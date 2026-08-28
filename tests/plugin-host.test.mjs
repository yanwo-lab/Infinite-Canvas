import assert from 'node:assert/strict';
import test from 'node:test';

import {PluginHost, normalizeExecutionResult, normalizePortDefinitions} from '../static/js/plugin-host.js';

function makeHost(overrides={}) {
    const nodes = [];
    const connections = [];
    const host = new PluginHost({
        getNodes:() => nodes,
        getConnections:() => connections,
        requestRender:() => {},
        requestSave:() => {},
        toast:() => {},
        log:() => {},
        ...overrides,
    });
    return {host, nodes, connections};
}

test('registers and creates a node without exposing canvas internals', () => {
    const {host, nodes} = makeHost();
    host.registerNode({
        type:'example-text', title:'Example Text', category:'Examples', icon:'type',
        create:() => ({text:'hello'}), render:() => '<input>', bindUI:() => {},
        inputs:[{id:'input', type:'text'}], outputs:[{id:'output', type:'text'}],
        execute:({node}) => ({outputs:{output:[{type:'text', value:node.text}]}}),
        serialize:node => ({text:node.text}), deserialize:data => ({text:data.text}),
    });

    const node = host.createNode('example-text', {x:10, y:20});

    assert.equal(node.type, 'plugin:example-text');
    assert.equal(node.text, 'hello');
    assert.equal(nodes.length, 1);
    assert.equal(host.getNode(node.id).id, node.id);
    assert.equal(host.getNode(node.id).x, 10);
});

test('isolates plugin lifecycle errors', async () => {
    const errors = [];
    const {host, nodes} = makeHost({log:(level, message) => errors.push([level, message])});
    host.registerNode({
        type:'broken', title:'Broken', create:() => { throw new Error('create failed'); },
        render:() => { throw new Error('render failed'); },
        bindUI:() => { throw new Error('bind failed'); },
        execute:() => { throw new Error('execute failed'); },
        serialize:() => { throw new Error('serialize failed'); },
        deserialize:() => { throw new Error('deserialize failed'); },
    });

    const node = host.createNode('broken');
    nodes.push({id:'saved', type:'plugin:broken', pluginData:{untouched:true}});

    assert.equal(node.pluginError.stage, 'create');
    assert.match(host.renderNode(node), /Plugin error/);
    assert.equal((await host.executeNode(nodes[1], {})).error.stage, 'execute');
    assert.deepEqual(host.serializeNode(nodes[1]).pluginData, {untouched:true});
    assert.ok(errors.length >= 3);
});

test('executes upstream text through typed ports and preserves multi-output protocol', async () => {
    const {host, nodes, connections} = makeHost();
    host.registerNode({
        type:'example-text', title:'Example Text',
        create:() => ({text:''}), render:() => '', bindUI:() => {},
        inputs:[{id:'input', type:'text'}], outputs:[{id:'output', type:'text'}],
        execute:({node, inputs}) => ({
            outputs:{output:[{type:'text', value:`Example: ${inputs.input?.[0]?.value || node.text}`}]},
            flow:{continue:['output']}, repeat:[],
        }),
    });
    const first = host.createNode('example-text');
    first.text = 'A';
    const second = host.createNode('example-text');
    connections.push({from:first.id, to:second.id, kind:'flow', fromPort:'output', toPort:'input'});

    const firstResult = await host.executeNode(first, {});
    const secondInputs = host.collectInputs(second, new Map([[first.id, firstResult]]));
    const secondResult = await host.executeNode(second, secondInputs);

    assert.equal(secondResult.outputs.output[0].value, 'Example: Example: A');
    assert.deepEqual(secondResult.flow.continue, ['output']);
    assert.deepEqual(secondResult.repeat, []);
});

test('normalizes the minimal execution subset for future flow and repeat controls', () => {
    assert.deepEqual(normalizeExecutionResult({outputs:{left:[{type:'text', value:'x'}]}}), {
        outputs:{left:[{type:'text', value:'x'}]}, flow:{continue:['left']}, repeat:[], meta:{},
    });
});

test('Example Text plugin exposes editable UI and chooses upstream text over local text', async () => {
    const registered = [];
    const module = await import('../plugins/example-text/index.js');
    await module.activate({registerNode:definition => registered.push(definition)});
    const definition = registered[0];

    assert.equal(definition.type, 'example-text');
    assert.match(definition.render({node:{text:'local'}}), /textarea/);
    assert.match(definition.render({node:{text:'local'}}), /button/);
    assert.equal((await definition.execute({node:{text:'local'}, inputs:{}})).outputs.output[0].value, 'Example: local');
    assert.equal((await definition.execute({node:{text:'local'}, inputs:{input:[{type:'text', value:'upstream'}]}})).outputs.output[0].value, 'Example: upstream');
    assert.deepEqual(definition.deserialize({text:'saved'}), {text:'saved', output:''});
});

test('executes a connected plugin graph in upstream order', async () => {
    const {host, nodes, connections} = makeHost();
    const order = [];
    host.registerNode({
        type:'text', title:'Text', create:({options}) => ({text:options.text || ''}),
        execute:({node, inputs}) => {
            order.push(node.text);
            return {outputs:{output:[{type:'text', value:inputs.input?.[0]?.value || node.text}]}};
        },
    });
    const first = host.createNode('text', {text:'first'});
    const second = host.createNode('text', {text:'second'});
    connections.push({from:first.id, to:second.id, kind:'input', fromPort:'output', toPort:'input'});

    const results = await host.executeGraph(second.id);

    assert.deepEqual(order, ['first', 'second']);
    assert.equal(results.get(second.id).outputs.output[0].value, 'first');
});

test('isolates module import and activation failures while loading remaining plugins', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async () => ({ok:true, json:async () => ({plugins:[
        {id:'import-broken', moduleUrl:'/broken.js'},
        {id:'activate-broken', moduleUrl:'/activate.js'},
        {id:'valid', moduleUrl:'/valid.js'},
    ]})});
    const {host} = makeHost();
    const importer = async url => {
        if(url === '/broken.js') throw new Error('bad module');
        if(url === '/activate.js') return {activate:async () => { throw new Error('bad activation'); }};
        return {activate:async facade => facade.registerNode({type:'valid', title:'Valid'})};
    };
    try {
        const result = await host.loadFromApi('/api/plugins', importer, null);
        assert.deepEqual(result.plugins.map(plugin => plugin.id), ['valid']);
        assert.equal(result.errors.length, 2);
        assert.equal(host.getNodeDefinition('valid').title, 'Valid');
    } finally {
        globalThis.fetch = originalFetch;
    }
});

test('unknown plugin nodes round-trip without adding or dropping fields', () => {
    const {host} = makeHost();
    const raw = {id:'missing', type:'plugin:not-installed', x:4, custom:{opaque:true}};
    assert.deepEqual(host.serializeNode(host.deserializeNode(raw)), raw);
    assert.match(host.renderNode(raw), /Unknown Plugin Node/);
});

test('updates editable state without forcing a render when a plugin requests it', () => {
    let renders = 0;
    let saves = 0;
    const {host, nodes} = makeHost({requestRender:() => renders++, requestSave:() => saves++});
    nodes.push({id:'editable', type:'plugin:editable', text:''});

    host.updateNode('editable', {text:'typing'}, {render:false});

    assert.equal(nodes[0].text, 'typing');
    assert.equal(renders, 0);
    assert.equal(saves, 1);
});

test('normalizes named input and output ports for the canvas UI', () => {
    assert.deepEqual(normalizePortDefinitions([{id:'left', type:'text'}, {id:'right', label:'Right'}], 'output'), [
        {id:'left', label:'left', type:'text', direction:'output'},
        {id:'right', label:'Right', type:'any', direction:'output'},
    ]);
    assert.deepEqual(normalizePortDefinitions([], 'input'), []);
    assert.deepEqual(normalizePortDefinitions(undefined, 'input'), [
        {id:'input', label:'input', type:'any', direction:'input'},
    ]);
});
test('restoring a missing plugin preserves its saved record without persisting hydration state', async () => {
    const {host} = makeHost();
    const raw = {
        id:'saved-list', type:'plugin:list', x:7,
        custom:{opaque:true}, pluginData:{items:['first', 'second']},
    };

    assert.deepEqual(host.serializeNode(host.deserializeNode(raw)), raw);

    const {activate} = await import('../plugins/list/index.js');
    await activate(host._facade());
    const restored = host.deserializeNode(raw);

    assert.deepEqual(restored.items, ['first', 'second']);
    assert.deepEqual(restored.custom, {opaque:true});
    assert.equal(Object.hasOwn(restored, 'unknownPlugin'), false);
});
