const PLUGIN_NODE_PREFIX = 'plugin:';

function clone(value) {
    if(value === undefined) return undefined;
    return JSON.parse(JSON.stringify(value));
}

function pluginNodeType(type) {
    return String(type || '').startsWith(PLUGIN_NODE_PREFIX) ? String(type) : `${PLUGIN_NODE_PREFIX}${type}`;
}

function definitionType(nodeOrType) {
    const type = typeof nodeOrType === 'string' ? nodeOrType : nodeOrType?.type;
    return String(type || '').startsWith(PLUGIN_NODE_PREFIX) ? String(type).slice(PLUGIN_NODE_PREFIX.length) : '';
}

function errorResult(stage, error) {
    return {stage, message:error?.message || String(error)};
}

function abortedResult(signal) {
    const reason = signal?.reason;
    return {stage:'aborted', message:reason?.message || String(reason || 'Workflow execution aborted')};
}

export function normalizePortDefinitions(ports, direction) {
    const fallbackId = direction === 'output' ? 'output' : 'input';
    const source = Array.isArray(ports) ? ports : [{id:fallbackId}];
    return source.map(port => {
        const id = String(port?.id || fallbackId);
        return {id, label:String(port?.label || id), type:String(port?.type || 'any'), direction};
    });
}

export function normalizeExecutionResult(result={}) {
    const outputs = result?.outputs && typeof result.outputs === 'object' ? result.outputs : {};
    const ports = Object.keys(outputs);
    return {
        outputs,
        flow:{continue:Array.isArray(result?.flow?.continue) ? result.flow.continue : ports},
        repeat:Array.isArray(result?.repeat) ? result.repeat : [],
        meta:result?.meta && typeof result.meta === 'object' ? result.meta : {},
        ...(result?.error ? {error:result.error} : {}),
    };
}

export class PluginHost {
    constructor(adapter={}) {
        this.adapter = adapter;
        this.nodeTypes = new Map();
        this.plugins = new Map();
        this.pluginDisposers = new Map();
        this.toolbarItems = new Map();
        this.loadErrors = [];
        this.uiDocument = null;
    }

    _log(stage, error, detail='') {
        const message = `[plugins] ${stage}${detail ? ` (${detail})` : ''}: ${error?.message || error}`;
        this.adapter.log?.('error', message, error);
        return errorResult(stage, error);
    }

    registerNode(definition) {
        const type = String(definition?.type || '').trim();
        if(!type) throw new Error('Plugin node type is required');
        if(this.nodeTypes.has(type)) throw new Error(`Plugin node type already registered: ${type}`);
        this.nodeTypes.set(type, Object.freeze({...definition, type}));
        return () => this.nodeTypes.delete(type);
    }

    getNodeDefinition(nodeOrType) { return this.nodeTypes.get(definitionType(nodeOrType) || String(nodeOrType || '')); }
    listNodeDefinitions() { return [...this.nodeTypes.values()]; }
    isPluginNode(node) { return Boolean(definitionType(node)); }
    isKnownNode(node) { return Boolean(this.getNodeDefinition(node)); }
    getNodePorts(node, direction) {
        const definition = this.getNodeDefinition(node);
        return normalizePortDefinitions(definition?.[direction === 'output' ? 'outputs' : 'inputs'], direction);
    }
    canConnect(fromNode, fromPort, toNode, toPort) {
        if(!this.isKnownNode(fromNode) || !this.isKnownNode(toNode)) return true;
        const output = this.getNodePorts(fromNode, 'output').find(port => port.id === fromPort);
        const input = this.getNodePorts(toNode, 'input').find(port => port.id === toPort);
        if(!output || !input) return false;
        return output.type === 'any' || input.type === 'any' || output.type === input.type;
    }

    createNode(type, options={}) {
        const definition = this.getNodeDefinition(type);
        if(!definition) throw new Error(`Unknown plugin node type: ${type}`);
        this.adapter.beforeMutation?.();
        let state = {};
        let pluginError;
        try { state = definition.create?.({host:this._facade(), options:clone(options)}) || {}; }
        catch(error) { pluginError = this._log('create', error, definition.type); }
        const node = {
            id:options.id || `plugin-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
            type:pluginNodeType(definition.type), x:Number(options.x) || 0, y:Number(options.y) || 0,
            title:definition.title || definition.type, created_at:Date.now(), ...clone(state),
        };
        if(pluginError) node.pluginError = pluginError;
        this.adapter.getNodes?.().push(node);
        this.adapter.requestRender?.();
        this.adapter.requestSave?.();
        return node;
    }

    updateNode(id, patch, options={}) {
        const node = this.adapter.getNodes?.().find(item => item.id === id);
        if(!node) return null;
        Object.assign(node, clone(patch || {}));
        if(options.render !== false) this.adapter.requestRender?.();
        this.adapter.requestSave?.();
        return clone(node);
    }

    getNode(id) { return clone(this.adapter.getNodes?.().find(item => item.id === id) || null); }
    getIncomingConnections(id) { return clone((this.adapter.getConnections?.() || []).filter(item => item.to === id)); }
    getOutgoingConnections(id) { return clone((this.adapter.getConnections?.() || []).filter(item => item.from === id)); }

    mountUI(documentRef=globalThis.document) {
        this.uiDocument = documentRef || null;
        for(const item of this.toolbarItems.values()) this._mountToolbarItem(item);
    }

    registerToolbarItem(definition, pluginId='plugin') {
        const id = String(definition?.id || '').trim();
        if(!id) throw new Error('Toolbar item id is required');
        const owner = String(pluginId || 'plugin');
        const key = `${owner}:${id}`;
        if(this.toolbarItems.has(key)) throw new Error(`Toolbar item already registered: ${key}`);
        const item = {key, pluginId:owner, definition:{...definition, id}, element:null};
        this.toolbarItems.set(key, item);
        this._mountToolbarItem(item);
        return () => {
            item.element?.remove?.();
            this.toolbarItems.delete(key);
        };
    }

    _mountToolbarItem(item) {
        if(item.element || !this.uiDocument?.createElement) return;
        const slot = this.adapter.getUISlot?.('toolbar');
        if(!slot?.appendChild) return;
        const button = this.uiDocument.createElement('button');
        button.type = 'button';
        button.className = 'plugin-toolbar-item';
        button.dataset.pluginToolbarItem = item.key;
        button.textContent = String(item.definition.label || item.definition.id);
        button.title = String(item.definition.title || item.definition.label || item.definition.id);
        button.addEventListener('click', event => {
            try { item.definition.onClick?.({event, host:this._facade({id:item.pluginId})}); }
            catch(error) { this._log('toolbar click', error, item.key); }
        });
        slot.appendChild(button);
        item.element = button;
    }

    unloadPlugin(pluginId) {
        const id = String(pluginId || '');
        const disposers = this.pluginDisposers.get(id) || [];
        for(const dispose of [...disposers].reverse()) {
            try { dispose?.(); }
            catch(error) { this._log('unload', error, id); }
        }
        this.pluginDisposers.delete(id);
        this.plugins.delete(id);
    }

    renderNode(node) {
        const definition = this.getNodeDefinition(node);
        if(!definition) return this.renderUnknownNode(node);
        try { return String(definition.render?.({node:clone(node), host:this._facade()}) || ''); }
        catch(error) {
            const failure = this._log('render', error, definition.type);
            return `<div class="plugin-node-error">Plugin error: ${this.escapeHtml(failure.message)}</div>`;
        }
    }

    bindNodeUI(element, node) {
        const definition = this.getNodeDefinition(node);
        if(!definition) return;
        try { definition.bindUI?.({element, node:clone(node), host:this._facade()}); }
        catch(error) { this._log('bindUI', error, definition.type); }
    }

    async executeNode(node, inputs={}, context={}) {
        const definition = this.getNodeDefinition(node);
        if(!definition) return normalizeExecutionResult({error:{stage:'execute', message:`Missing plugin node: ${definitionType(node)}`}});
        try {
            return normalizeExecutionResult(await definition.execute?.({node:clone(node), inputs:clone(inputs), context, host:this._facade()}));
        } catch(error) {
            return normalizeExecutionResult({error:this._log('execute', error, definition.type)});
        }
    }

    collectInputs(node, results) {
        const inputs = {};
        for(const connection of this.getIncomingConnections(node.id)) {
            const outputPort = connection.fromPort || 'output';
            const inputPort = connection.toPort || 'input';
            const values = results.get(connection.from)?.outputs?.[outputPort] || [];
            inputs[inputPort] = [...(inputs[inputPort] || []), ...clone(values)];
        }
        return inputs;
    }

    async executeGraph(targetNodeId, context={}) {
        const results = new Map();
        const visiting = new Set();
        const run = async nodeId => {
            if(results.has(nodeId)) return results.get(nodeId);
            if(visiting.has(nodeId)) throw new Error('Plugin workflow contains a cycle');
            if(context?.signal?.aborted) {
                const result = normalizeExecutionResult({error:abortedResult(context.signal)});
                results.set(nodeId, result);
                return result;
            }
            visiting.add(nodeId);
            const node = this.adapter.getNodes?.().find(item => item.id === nodeId);
            if(!node || !this.isPluginNode(node)) throw new Error(`Plugin node not found: ${nodeId}`);
            for(const connection of this.getIncomingConnections(nodeId)) {
                const upstream = this.adapter.getNodes?.().find(item => item.id === connection.from);
                if(upstream && this.isPluginNode(upstream)) {
                    const upstreamResult = await run(upstream.id);
                    if(upstreamResult?.error) {
                        visiting.delete(nodeId);
                        return upstreamResult;
                    }
                }
            }
            if(context?.signal?.aborted) {
                const result = normalizeExecutionResult({error:abortedResult(context.signal)});
                results.set(nodeId, result);
                visiting.delete(nodeId);
                return result;
            }
            const result = await this.executeNode(node, this.collectInputs(node, results), context);
            results.set(nodeId, result);
            visiting.delete(nodeId);
            return result;
        };
        await run(targetNodeId);
        return results;
    }

    async executeWorkflow(startNodeId, context={}) {
        const executionContext = {
            ...context,
            runId:String(context.runId || `plugin-run-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`),
            signal:context.signal || null,
            logger:context.logger || ((level, message, detail) => this.adapter.log?.(level, message, detail)),
        };
        const results = await this.executeGraph(startNodeId, executionContext);
        const startNode = this.adapter.getNodes?.().find(item => item.id === startNodeId);
        const startResult = results.get(startNodeId);
        const upstreamError = [...results.values()].find(result => result?.error)?.error;
        const execution = {context:executionContext, results, runs:[], error:upstreamError || startResult?.error || null};
        if(!startNode || !startResult || execution.error) return execution;
        await this._dispatchResult(startNode, startResult, results, executionContext, execution, true);
        return execution;
    }

    async _dispatchResult(sourceNode, sourceResult, baseResults, context, execution, allowSingle=true) {
        if(execution.error) return;
        if(context?.signal?.aborted) {
            execution.error = abortedResult(context.signal);
            return;
        }
        const isRepeat = sourceResult.repeat.length > 0 || sourceResult.meta?.repeat === true;
        const frames = isRepeat ? sourceResult.repeat : (allowSingle ? [{outputs:sourceResult.outputs, context:{}}] : []);
        for(const [iteration, frame] of frames.entries()) {
            if(execution.error) return;
            const frameOutputs = frame?.outputs && typeof frame.outputs === 'object' ? frame.outputs : {};
            const continuedPorts = new Set(Array.isArray(sourceResult.flow?.continue) ? sourceResult.flow.continue : Object.keys(frameOutputs));
            const outgoing = this.getOutgoingConnections(sourceNode.id).filter(connection => {
                const port = connection.fromPort || 'output';
                return continuedPorts.has(port) && Object.hasOwn(frameOutputs, port);
            });
            const targets = new Map();
            for(const connection of outgoing) {
                if(!targets.has(connection.to)) targets.set(connection.to, []);
                targets.get(connection.to).push(connection);
            }
            for(const [targetId, sourceConnections] of targets) {
                if(context?.signal?.aborted) {
                    execution.error = abortedResult(context.signal);
                    return;
                }
                const target = this.adapter.getNodes?.().find(item => item.id === targetId);
                if(!target || !this.isPluginNode(target)) continue;
                const inputs = this.collectInputs(target, baseResults);
                for(const connection of sourceConnections) {
                    const inputPort = connection.toPort || 'input';
                    const outputPort = connection.fromPort || 'output';
                    inputs[inputPort] = clone(frameOutputs[outputPort] || []);
                }
                const runContext = {
                    ...context,
                    ...(frame?.context && typeof frame.context === 'object' ? clone(frame.context) : {}),
                    ...(isRepeat ? {repeat:{sourceNodeId:sourceNode.id, key:String(frame?.key ?? iteration), iteration}} : {}),
                };
                const result = await this.executeNode(target, inputs, runContext);
                execution.runs.push({nodeId:target.id, context:clone(runContext), result});
                if(result.error) {
                    execution.error = result.error;
                    return;
                }
                const nextResults = new Map(baseResults);
                nextResults.set(target.id, result);
                await this._dispatchResult(target, result, nextResults, runContext, execution, true);
            }
        }
    }

    serializeNode(node) {
        const definition = this.getNodeDefinition(node);
        if(!definition) return clone(node);
        try {
            const pluginData = definition.serialize ? definition.serialize(clone(node)) : clone(node.pluginData || {});
            return {...clone(node), pluginData:clone(pluginData)};
        } catch(error) {
            this._log('serialize', error, definition.type);
            return clone(node);
        }
    }

    deserializeNode(raw) {
        const definition = this.getNodeDefinition(raw);
        if(!definition) return clone(raw);
        try {
            const state = definition.deserialize ? definition.deserialize(clone(raw.pluginData ?? raw)) : clone(raw.pluginData || {});
            return {...clone(raw), ...clone(state), unknownPlugin:false};
        } catch(error) {
            return {...clone(raw), pluginError:this._log('deserialize', error, definition.type)};
        }
    }

    renderUnknownNode(node) {
        const type = definitionType(node) || node?.type || 'unknown';
        return `<div class="unknown-plugin-node"><strong>Unknown Plugin Node</strong><span>${this.escapeHtml(type)}</span><small>插件缺失，原始数据已保留</small></div>`;
    }

    async loadFromApi(url='/api/plugins', importer=value => import(value), documentRef=globalThis.document) {
        this.mountUI(documentRef);
        let response;
        try {
            response = await fetch(url);
            if(!response.ok) throw new Error(`plugin discovery returned ${response.status}`);
            response = await response.json();
        } catch(error) {
            this.loadErrors.push(this._log('discovery', error));
            return {plugins:[], errors:this.loadErrors};
        }
        for(const manifest of response.plugins || []) {
            const disposers = [];
            try {
                if(this.plugins.has(manifest.id)) this.unloadPlugin(manifest.id);
                for(const styleUrl of manifest.styleUrls || []) {
                    const dispose = this.loadStyle(styleUrl, manifest.id, documentRef);
                    if(dispose) disposers.push(dispose);
                }
                const module = await importer(manifest.moduleUrl);
                if(typeof module.activate !== 'function') throw new Error('activate(host) export is required');
                try { await module.activate(this._facade(manifest, disposers)); }
                catch(error) { throw Object.assign(error, {pluginStage:'activate'}); }
                this.plugins.set(manifest.id, manifest);
                this.pluginDisposers.set(manifest.id, disposers);
            } catch(error) {
                for(const dispose of [...disposers].reverse()) {
                    try { dispose?.(); } catch(_) {}
                }
                this.plugins.delete(manifest.id);
                this.pluginDisposers.delete(manifest.id);
                const stage = error?.pluginStage || 'module import';
                this.loadErrors.push(this._log(stage, error, manifest.id));
            }
        }
        return {plugins:[...this.plugins.values()], errors:[...(response.errors || []), ...this.loadErrors]};
    }

    loadStyle(url, pluginId, documentRef=globalThis.document) {
        if(!documentRef?.head || documentRef.querySelector?.(`link[data-plugin-style="${pluginId}:${url}"]`)) return null;
        const link = documentRef.createElement('link');
        link.rel = 'stylesheet'; link.href = url; link.dataset.pluginStyle = `${pluginId}:${url}`;
        link.onerror = error => this._log('style', error, pluginId);
        documentRef.head.appendChild(link);
        return () => link.remove?.();
    }

    escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
    }

    _facade(manifest=null, disposers=null) {
        const track = dispose => {
            if(disposers && typeof dispose === 'function') disposers.push(dispose);
            return dispose;
        };
        return Object.freeze({
            manifest:manifest ? clone(manifest) : undefined,
            registerNode:definition => track(this.registerNode(definition)), updateNode:this.updateNode.bind(this), getNode:this.getNode.bind(this),
            registerToolbarItem:definition => track(this.registerToolbarItem(definition, manifest?.id)),
            requestRender:() => this.adapter.requestRender?.(), requestSave:() => this.adapter.requestSave?.(),
            getIncomingConnections:this.getIncomingConnections.bind(this), getOutgoingConnections:this.getOutgoingConnections.bind(this),
            toast:message => this.adapter.toast?.(message), log:(level, message, detail) => this.adapter.log?.(level, message, detail),
        });
    }
}
