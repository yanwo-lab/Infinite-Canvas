import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';

import {PluginHost} from '../static/js/plugin-host.js';
import {activate} from '../plugins/yanwo-ui/index.js';

function fakeUI() {
    const slot = {
        children:[],
        appendChild(element) { this.children.push(element); element.parentNode = this; },
    };
    const head = {
        children:[],
        appendChild(element) { this.children.push(element); element.parentNode = this; },
    };
    const document = {
        head,
        createElement:() => ({
            dataset:{},
            listeners:{},
            addEventListener(name, callback) { this.listeners[name] = callback; },
            remove() {
                if(this.parentNode) this.parentNode.children = this.parentNode.children.filter(item => item !== this);
            },
        }),
    };
    return {slot, document};
}

test('Yanwo UI mounts an accessible workspace control without changing canvas data', async () => {
    const {slot, document} = fakeUI();
    const nodes = [{id:'adapter-node', type:'plugin:list'}];
    const connections = [{from:'adapter-node', to:'next-node', kind:'flow'}];
    const toasts = [];
    const host = new PluginHost({
        getUISlot:name => name === 'toolbar' ? slot : null,
        getNodes:() => nodes,
        getConnections:() => connections,
        toast:message => toasts.push(message),
    });
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async () => ({ok:true, json:async () => ({plugins:[{
        id:'yanwo-ui', moduleUrl:'/plugins/yanwo-ui/index.js', styleUrls:['/plugins/yanwo-ui/style.css'],
    }]})});

    try {
        const loaded = await host.loadFromApi('/api/plugins', async () => ({activate}), document);

        assert.deepEqual(loaded.plugins.map(plugin => plugin.id), ['yanwo-ui']);
        assert.equal(document.head.children.length, 1);
        assert.equal(document.head.children[0].dataset.pluginStyle, 'yanwo-ui:/plugins/yanwo-ui/style.css');
        assert.equal(slot.children.length, 1);
        assert.equal(slot.children[0].type, 'button');
        assert.equal(slot.children[0].textContent, 'Yanwo UI');
        assert.match(slot.children[0].title, /Yanwo UI workspace/i);
        slot.children[0].listeners.click();
        assert.deepEqual(toasts, ['Yanwo UI workspace presentation is active']);
        assert.deepEqual(nodes, [{id:'adapter-node', type:'plugin:list'}]);
        assert.deepEqual(connections, [{from:'adapter-node', to:'next-node', kind:'flow'}]);

        host.unloadPlugin('yanwo-ui');
        assert.equal(slot.children.length, 0);
        assert.equal(document.head.children.length, 0);
    } finally {
        globalThis.fetch = originalFetch;
    }
});

test('Yanwo UI manifest declares independently discoverable module and stylesheet', async () => {
    const manifest = JSON.parse(await readFile(
        new URL('../plugins/yanwo-ui/plugin.json', import.meta.url), 'utf8',
    ));

    assert.equal(manifest.main, 'index.js');
    assert.deepEqual(manifest.styles, ['style.css']);
});
