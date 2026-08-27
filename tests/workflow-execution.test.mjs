import assert from 'node:assert/strict';
import test from 'node:test';

import {PluginHost} from '../static/js/plugin-host.js';
import {activate as activateForEach} from '../plugins/for-each/index.js';
import {activate as activateIf} from '../plugins/if/index.js';
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
    return {host, connections};
}

async function combinedWorkflow(values=[true, false, true]) {
    const {host, connections} = makeHost();
    const observed = [];
    host.registerNode({
        type:'boolean-list-source', inputs:[], outputs:[{id:'output', type:'list'}],
        create:() => ({values}),
        execute:({node}) => ({outputs:{output:[{type:'list', itemType:'boolean', value:node.values}]}}),
    });
    await activateList(host._facade());
    await activateForEach(host._facade());
    await activateIf(host._facade());
    for(const branch of ['true', 'false']) host.registerNode({
        type:`sink-${branch}`, inputs:[{id:'input', type:'any'}], outputs:[], create:() => ({}),
        execute:({inputs, context, node}) => {
            if(node.fail === true) throw new Error(`${branch} failed`);
            observed.push({
                branch,
                value:inputs.input[0].value,
                index:context.index,
                repeatIteration:context.repeat?.iteration,
                repeatSource:context.repeat?.sourceNodeId,
                runId:context.runId,
            });
            return {outputs:{}};
        },
    });
    const source = host.createNode('boolean-list-source');
    const list = host.createNode('list');
    const each = host.createNode('for-each');
    const branch = host.createNode('if');
    const yes = host.createNode('sink-true');
    const no = host.createNode('sink-false');
    connections.push(
        {from:source.id, to:list.id, fromPort:'output', toPort:'input'},
        {from:list.id, to:each.id, fromPort:'list', toPort:'collection'},
        {from:each.id, to:branch.id, fromPort:'item', toPort:'condition'},
        {from:branch.id, to:yes.id, fromPort:'true', toPort:'input'},
        {from:branch.id, to:no.id, fromPort:'false', toPort:'input'},
    );
    return {host, observed, each, yes, no};
}

test('List, For Each, and IF compose with ordered data, loop, and branch semantics', async () => {
    const {host, observed, each} = await combinedWorkflow();

    const execution = await host.executeWorkflow(each.id);

    assert.equal(execution.error, null);
    assert.deepEqual(observed.map(({branch, value, index}) => ({branch, value, index})), [
        {branch:'true', value:true, index:0},
        {branch:'false', value:false, index:1},
        {branch:'true', value:true, index:2},
    ]);
    assert.equal(new Set(observed.map(item => item.runId)).size, 1);
    assert.equal(observed[0].runId, execution.context.runId);
    assert.deepEqual(observed.map(item => item.repeatIteration), [0, 1, 2]);
    assert.deepEqual(new Set(observed.map(item => item.repeatSource)), new Set([each.id]));
});

test('an already aborted workflow executes no plugin and returns an aborted error', async () => {
    const {host, observed, each} = await combinedWorkflow();
    const controller = new AbortController();
    controller.abort('cancelled by test');

    const execution = await host.executeWorkflow(each.id, {signal:controller.signal});

    assert.deepEqual(observed, []);
    assert.equal(execution.error.stage, 'aborted');
    assert.equal(execution.context.signal, controller.signal);
});

test('a failed run does not pollute a clean subsequent run', async () => {
    const {host, observed, each, no} = await combinedWorkflow();
    no.fail = true;

    const failed = await host.executeWorkflow(each.id, {runId:'failed-run'});
    no.fail = false;
    observed.length = 0;
    const recovered = await host.executeWorkflow(each.id, {runId:'recovered-run'});

    assert.equal(failed.error.message, 'false failed');
    assert.equal(recovered.error, null);
    assert.deepEqual(observed.map(item => item.index), [0, 1, 2]);
    assert.deepEqual(new Set(observed.map(item => item.runId)), new Set(['recovered-run']));
});
