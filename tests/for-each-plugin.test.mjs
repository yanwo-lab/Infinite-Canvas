import assert from 'node:assert/strict';
import test from 'node:test';

import {PluginHost} from '../static/js/plugin-host.js';
import {activate as activateExampleText} from '../plugins/example-text/index.js';
import {activate as activateForEach} from '../plugins/for-each/index.js';
import {activate as activateList} from '../plugins/list/index.js';

function makeHost() {
    const nodes = [];
    const connections = [];
    const host = new PluginHost({
        getNodes:() => nodes,
        getConnections:() => connections,
        requestRender:() => {},
        requestSave:() => {},
        log:() => {},
    });
    return {host, nodes, connections};
}

async function registeredForEach() {
    const definitions = [];
    await activateForEach({registerNode:definition => definitions.push(definition)});
    return definitions[0];
}

test('For Each emits ordered repeat frames with typed item and index values', async () => {
    const definition = await registeredForEach();
    const result = await definition.execute({inputs:{collection:[{
        type:'list', itemType:'text', value:['A', 'B', 'C'],
    }]}});

    assert.deepEqual(result.repeat, [
        {key:'0', outputs:{item:[{type:'text', value:'A'}], index:[{type:'number', value:0}]}, context:{index:0, length:3, first:true, last:false}},
        {key:'1', outputs:{item:[{type:'text', value:'B'}], index:[{type:'number', value:1}]}, context:{index:1, length:3, first:false, last:false}},
        {key:'2', outputs:{item:[{type:'text', value:'C'}], index:[{type:'number', value:2}]}, context:{index:2, length:3, first:false, last:true}},
    ]);
});

test('For Each gives empty and single-item collections explicit repeat semantics', async () => {
    const definition = await registeredForEach();
    const empty = await definition.execute({inputs:{collection:[{type:'list', itemType:'text', value:[]}]}});
    const single = await definition.execute({inputs:{collection:[{type:'list', itemType:'number', value:[7]}]}});

    assert.deepEqual(empty.repeat, []);
    assert.deepEqual(single.repeat, [{
        key:'0',
        outputs:{item:[{type:'number', value:7}], index:[{type:'number', value:0}]},
        context:{index:0, length:1, first:true, last:true},
    }]);
});

test('List to For Each to Example Text executes downstream once per item in order', async () => {
    const {host, connections} = makeHost();
    await activateList(host._facade());
    await activateForEach(host._facade());
    await activateExampleText(host._facade());
    const list = host.createNode('list');
    list.items = ['A', 'B', 'C'];
    const each = host.createNode('for-each');
    const example = host.createNode('example-text');
    connections.push(
        {from:list.id, to:each.id, fromPort:'list', toPort:'collection'},
        {from:each.id, to:example.id, fromPort:'item', toPort:'input'},
    );

    const execution = await host.executeWorkflow(each.id);

    assert.deepEqual(execution.runs.filter(run => run.nodeId === example.id).map(run => run.result.outputs.output[0].value), [
        'Example: A', 'Example: B', 'Example: C',
    ]);
    assert.deepEqual(execution.runs.filter(run => run.nodeId === example.id).map(run => run.context.index), [0, 1, 2]);
    assert.equal(execution.error, null);
});

test('generic repeat dispatch does not execute downstream for an empty collection', async () => {
    const {host, connections} = makeHost();
    await activateList(host._facade());
    await activateForEach(host._facade());
    await activateExampleText(host._facade());
    const list = host.createNode('list');
    const each = host.createNode('for-each');
    const example = host.createNode('example-text');
    connections.push(
        {from:list.id, to:each.id, fromPort:'list', toPort:'collection'},
        {from:each.id, to:example.id, fromPort:'item', toPort:'input'},
    );

    const execution = await host.executeWorkflow(each.id);

    assert.deepEqual(execution.runs, []);
    assert.equal(execution.error, null);
});

test('generic repeat dispatch propagates a downstream plugin error and stops later items', async () => {
    const {host, connections} = makeHost();
    await activateList(host._facade());
    await activateForEach(host._facade());
    host.registerNode({
        type:'failing-consumer', inputs:[{id:'input', type:'any'}], outputs:[], create:() => ({}),
        execute:({inputs}) => {
            const value = inputs.input[0].value;
            if(value === 'B') throw new Error('B failed');
            return {outputs:{}};
        },
    });
    const list = host.createNode('list');
    list.items = ['A', 'B', 'C'];
    const each = host.createNode('for-each');
    const consumer = host.createNode('failing-consumer');
    connections.push(
        {from:list.id, to:each.id, fromPort:'list', toPort:'collection'},
        {from:each.id, to:consumer.id, fromPort:'item', toPort:'input'},
    );

    const execution = await host.executeWorkflow(each.id);

    assert.deepEqual(execution.runs.map(run => run.context.index), [0, 1]);
    assert.equal(execution.error.stage, 'execute');
    assert.equal(execution.error.message, 'B failed');
});

test('workflow propagates an upstream plugin error instead of treating it as an empty collection', async () => {
    const {host, connections} = makeHost();
    host.registerNode({
        type:'failing-source', inputs:[], outputs:[{id:'list', type:'list'}], create:() => ({}),
        execute:() => { throw new Error('upstream failed'); },
    });
    await activateForEach(host._facade());
    const source = host.createNode('failing-source');
    const each = host.createNode('for-each');
    connections.push({from:source.id, to:each.id, fromPort:'list', toPort:'collection'});

    const execution = await host.executeWorkflow(each.id);

    assert.equal(execution.error.stage, 'execute');
    assert.equal(execution.error.message, 'upstream failed');
    assert.deepEqual(execution.runs, []);
});

test('For Each state round-trips without depending on the built-in Loop node', async () => {
    const definition = await registeredForEach();
    assert.deepEqual(definition.create(), {});
    assert.deepEqual(definition.serialize({}), {});
    assert.deepEqual(definition.deserialize({}), {});
});
