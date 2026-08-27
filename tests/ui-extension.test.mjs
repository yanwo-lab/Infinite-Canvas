import assert from 'node:assert/strict';
import test from 'node:test';

import {PluginHost} from '../static/js/plugin-host.js';
import {activate as activateToolbarExample} from '../plugins/example-toolbar/index.js';

function fakeUI() {
    const slot = {
        children:[],
        appendChild(element) { this.children.push(element); element.parentNode = this; },
    };
    const document = {
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

test('a UI plugin mounts a control through the formal toolbar slot', async () => {
    const {slot, document} = fakeUI();
    const toasts = [];
    const host = new PluginHost({getUISlot:name => name === 'toolbar' ? slot : null, toast:message => toasts.push(message)});
    host.mountUI(document);

    await activateToolbarExample(host._facade({id:'example-toolbar'}));

    assert.equal(slot.children.length, 1);
    assert.equal(slot.children[0].textContent, 'Plugin Check');
    assert.equal(slot.children[0].dataset.pluginToolbarItem, 'example-toolbar:check');
    slot.children[0].listeners.click();
    assert.deepEqual(toasts, ['Example toolbar plugin is active']);
});

test('toolbar callback errors are isolated and leave the mounted control usable', () => {
    const {slot, document} = fakeUI();
    const errors = [];
    const host = new PluginHost({
        getUISlot:() => slot,
        log:(level, message) => errors.push([level, message]),
    });
    host.mountUI(document);
    host.registerToolbarItem({id:'broken', label:'Broken', onClick:() => { throw new Error('click failed'); }}, 'broken-plugin');

    assert.doesNotThrow(() => slot.children[0].listeners.click());
    assert.match(errors[0][1], /toolbar click/);
    assert.equal(slot.children.length, 1);
});

test('unregistering or omitting a UI plugin leaves the Canvas slot intact', () => {
    const {slot, document} = fakeUI();
    const host = new PluginHost({getUISlot:() => slot});
    host.mountUI(document);
    const unregister = host.registerToolbarItem({id:'temporary', label:'Temporary'}, 'optional-plugin');

    assert.equal(slot.children.length, 1);
    unregister();
    assert.equal(slot.children.length, 0);
    assert.ok(slot);
});

test('UI plugin manifest keeps CSS independently discoverable', async () => {
    const manifest = JSON.parse(await (await import('node:fs/promises')).readFile(
        new URL('../plugins/example-toolbar/plugin.json', import.meta.url), 'utf8',
    ));
    assert.deepEqual(manifest.styles, ['style.css']);
    assert.equal(manifest.main, 'index.js');
});

test('failed activation rolls back partial UI and permits a clean reload', async () => {
    const {slot, document} = fakeUI();
    const host = new PluginHost({getUISlot:() => slot, log:() => {}});
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async () => ({ok:true, json:async () => ({plugins:[{
        id:'recoverable', moduleUrl:'/recoverable.js', styleUrls:[],
    }]})});
    let fail = true;
    const importer = async () => ({activate:async facade => {
        facade.registerToolbarItem({id:'control', label:'Recovered'});
        if(fail) throw new Error('activate failed');
    }});
    try {
        const failed = await host.loadFromApi('/api/plugins', importer, document);
        assert.equal(failed.plugins.length, 0);
        assert.equal(slot.children.length, 0);
        assert.equal(host.toolbarItems.size, 0);

        fail = false;
        const recovered = await host.loadFromApi('/api/plugins', importer, document);
        assert.deepEqual(recovered.plugins.map(plugin => plugin.id), ['recoverable']);
        assert.equal(slot.children.length, 1);
    } finally {
        globalThis.fetch = originalFetch;
    }
});
