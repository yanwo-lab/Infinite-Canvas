import assert from 'node:assert/strict';
import test from 'node:test';

import {PluginHost} from '../static/js/plugin-host.js';
import {activate as activateIf} from '../plugins/if/index.js';

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

async function ifDefinition() {
    const definitions = [];
    await activateIf({registerNode:definition => definitions.push(definition)});
    return definitions[0];
}

test('IF selects exactly one named output for true and false boolean conditions', async () => {
    const definition = await ifDefinition();
    const whenTrue = await definition.execute({node:{condition:false}, inputs:{condition:[{type:'boolean', value:true}]}});
    const whenFalse = await definition.execute({node:{condition:true}, inputs:{condition:[{type:'boolean', value:false}]}});

    assert.deepEqual(whenTrue.flow.continue, ['true']);
    assert.deepEqual(whenTrue.outputs, {true:[{type:'boolean', value:true}], false:[]});
    assert.deepEqual(whenFalse.flow.continue, ['false']);
    assert.deepEqual(whenFalse.outputs, {true:[], false:[{type:'boolean', value:false}]});
});

test('IF uses its saved boolean when condition input is missing and rejects truthy coercion', async () => {
    const definition = await ifDefinition();
    const missing = await definition.execute({node:{condition:false}, inputs:{}});
    const nonBoolean = await definition.execute({node:{condition:true}, inputs:{condition:[{type:'text', value:'true'}]}});

    assert.deepEqual(missing.flow.continue, ['false']);
    assert.deepEqual(nonBoolean.flow.continue, ['true']);
    assert.equal(nonBoolean.meta.conditionSource, 'node');
});

test('boolean true executes only the true branch through named connection ports', async () => {
    const {host, connections} = makeHost();
    const observed = [];
    host.registerNode({
        type:'boolean-source', inputs:[], outputs:[{id:'output', type:'boolean'}],
        create:() => ({value:true}), execute:({node}) => ({outputs:{output:[{type:'boolean', value:node.value}]}}),
    });
    await activateIf(host._facade());
    for(const name of ['A', 'B']) host.registerNode({
        type:`consumer-${name}`, inputs:[{id:'input', type:'any'}], outputs:[], create:() => ({}),
        execute:({inputs}) => { observed.push([name, inputs.input[0].value]); return {outputs:{}}; },
    });
    const source = host.createNode('boolean-source');
    const branch = host.createNode('if');
    const yes = host.createNode('consumer-A');
    const no = host.createNode('consumer-B');
    connections.push(
        {from:source.id, to:branch.id, fromPort:'output', toPort:'condition'},
        {from:branch.id, to:yes.id, fromPort:'true', toPort:'input'},
        {from:branch.id, to:no.id, fromPort:'false', toPort:'input'},
    );

    const execution = await host.executeWorkflow(branch.id);

    assert.deepEqual(observed, [['A', true]]);
    assert.deepEqual(execution.runs.map(run => run.nodeId), [yes.id]);
    assert.equal(execution.error, null);
});

test('boolean false executes only the false branch and propagates its error', async () => {
    const {host, connections} = makeHost();
    await activateIf(host._facade());
    host.registerNode({
        type:'broken', inputs:[{id:'input', type:'any'}], outputs:[], create:() => ({}),
        execute:() => { throw new Error('false branch failed'); },
    });
    const branch = host.createNode('if');
    branch.condition = false;
    const broken = host.createNode('broken');
    connections.push({from:branch.id, to:broken.id, fromPort:'false', toPort:'input'});

    const execution = await host.executeWorkflow(branch.id);

    assert.equal(execution.runs.length, 1);
    assert.equal(execution.error.message, 'false branch failed');
});

test('legacy connections without port fields keep their default output/input behavior', async () => {
    const {host, connections} = makeHost();
    const received = [];
    host.registerNode({
        type:'legacy-source', create:() => ({}), execute:() => ({outputs:{output:[{type:'text', value:'legacy'}]}}),
    });
    host.registerNode({
        type:'legacy-target', create:() => ({}), execute:({inputs}) => {
            received.push(inputs.input[0].value);
            return {outputs:{}};
        },
    });
    const source = host.createNode('legacy-source');
    const target = host.createNode('legacy-target');
    connections.push({from:source.id, to:target.id, kind:'flow'});

    await host.executeWorkflow(source.id);

    assert.deepEqual(received, ['legacy']);
});

test('IF manual condition round-trips and exposes true/false ports', async () => {
    const definition = await ifDefinition();
    assert.deepEqual(definition.create(), {condition:false});
    assert.deepEqual(definition.deserialize(definition.serialize({condition:true})), {condition:true});
    assert.deepEqual(definition.outputs.map(port => port.id), ['true', 'false']);
});
