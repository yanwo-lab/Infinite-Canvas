import assert from 'node:assert/strict';
import test from 'node:test';

import {PluginHost} from '../static/js/plugin-host.js';
import {activate} from '../plugins/list/index.js';
import {readFile} from 'node:fs/promises';

async function listDefinition() {
    const registered = [];
    await activate({
        registerNode:definition => registered.push(definition),
        updateNode:() => {},
    });
    return registered[0];
}

test('List supports empty, single, and ordered text items', async () => {
    const definition = await listDefinition();

    assert.deepEqual(definition.create(), {items:[]});
    assert.deepEqual((await definition.execute({node:{items:[]}, inputs:{}})).outputs.list[0], {
        type:'list', itemType:'text', value:[],
    });
    assert.deepEqual((await definition.execute({node:{items:['one']}, inputs:{}})).outputs.list[0].value, ['one']);
    assert.deepEqual((await definition.execute({node:{items:['third', 'first', 'second']}, inputs:{}})).outputs.list[0].value, [
        'third', 'first', 'second',
    ]);
});

test('List converts upstream typed values without coupling to Loop', async () => {
    const definition = await listDefinition();
    const typedList = {type:'list', itemType:'text', value:['A', 'B']};

    assert.deepEqual((await definition.execute({node:{items:['local']}, inputs:{input:[typedList]}})).outputs.list[0], typedList);
    assert.deepEqual((await definition.execute({
        node:{items:['local']},
        inputs:{input:[{type:'text', value:'A\nB'}, {type:'number', value:3}, {type:'boolean', value:false}]},
    })).outputs.list[0], {type:'list', itemType:'text', value:['A', 'B', '3', 'false']});
});

test('List serialize and deserialize preserve content and order', async () => {
    const definition = await listDefinition();
    const saved = definition.serialize({items:['B', '', 'A']});

    assert.deepEqual(saved, {items:['B', '', 'A']});
    assert.deepEqual(definition.deserialize(saved), {items:['B', '', 'A']});
    assert.deepEqual(definition.deserialize({items:null}), {items:[]});
});

test('a downstream plugin receives the complete typed List through the host', async () => {
    const nodes = [];
    const connections = [];
    const host = new PluginHost({getNodes:() => nodes, getConnections:() => connections});
    await activate(host._facade());
    host.registerNode({
        type:'list-consumer', inputs:[{id:'collection', type:'list'}], outputs:[],
        create:() => ({}),
        execute:({inputs}) => ({outputs:{}, meta:{received:inputs.collection?.[0]}}),
    });
    const source = host.createNode('list');
    source.items = ['A', 'B', 'C'];
    const consumer = host.createNode('list-consumer');
    connections.push({from:source.id, to:consumer.id, fromPort:'list', toPort:'collection'});

    const results = await host.executeGraph(consumer.id);

    assert.deepEqual(results.get(consumer.id).meta.received, {
        type:'list', itemType:'text', value:['A', 'B', 'C'],
    });
});

test('List renders controls for adding, editing, deleting, and reordering items', async () => {
    const definition = await listDefinition();
    const html = definition.render({node:{items:['A', 'B']}});

    assert.match(html, /list-add-item/);
    assert.match(html, /list-item-value/);
    assert.match(html, /list-item-up/);
    assert.match(html, /list-item-down/);
    assert.match(html, /list-item-delete/);
    assert.match(html, /value="A"/);
    assert.match(html, /value="B"/);
});

test('List UI actions update items without exposing canvas internals', async () => {
    const node = {id:'list-1', items:['A', 'B']};
    const registered = [];
    const updates = [];
    await activate({
        registerNode:definition => registered.push(definition),
        getNode:() => node,
        updateNode:(id, patch, options) => {
            updates.push({id, patch, options});
            Object.assign(node, patch);
        },
    });
    const definition = registered[0];
    const control = () => ({addEventListener:(name, callback) => { if(name === 'click') callback(); }});
    const input = {addEventListener:(name, callback) => {
        if(name === 'input') callback({target:{value:'edited'}});
    }};
    const row = {
        dataset:{index:'0'},
        querySelector:selector => selector === '.list-item-value' ? input : control(),
    };
    const element = {
        querySelector:selector => selector === '.list-add-item' ? control() : null,
        querySelectorAll:() => [row],
    };

    definition.bindUI({element, node});

    assert.ok(updates.some(update => update.patch.items.at(-1) === ''));
    assert.ok(updates.some(update => update.patch.items.includes('edited') && update.options?.render === false));
    assert.ok(updates.some(update => update.patch.items.length < 3));
    assert.ok(updates.some(update => update.patch.items[0] === 'B'));
});

test('List plugin CSS targets the class emitted by the generic canvas renderer', async () => {
    const css = await readFile(new URL('../plugins/list/style.css', import.meta.url), 'utf8');
    assert.match(css, /\.plugin-node\.plugin-list/);
    assert.doesNotMatch(css, /data-plugin-type/);
});
