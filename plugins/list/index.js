function escapeAttribute(value) {
    return String(value ?? '').replace(/[&<>"']/g, character => ({
        '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;',
    }[character]));
}

function textItems(value) {
    if(!Array.isArray(value)) return [];
    return value.map(item => {
        if(typeof item === 'string') return item;
        if(item === null || item === undefined) return '';
        if(typeof item === 'object') {
            try { return JSON.stringify(item); }
            catch { return String(item); }
        }
        return String(item);
    });
}

function listFromInputs(inputs) {
    const values = Array.isArray(inputs?.input) ? inputs.input : [];
    const typedList = values.find(item => item?.type === 'list' && Array.isArray(item.value));
    if(typedList) {
        return {type:'list', itemType:String(typedList.itemType || 'text'), value:structuredClone(typedList.value)};
    }
    if(!values.length) return null;
    const items = [];
    for(const item of values) {
        if(item?.type === 'text') items.push(...String(item.value ?? '').split(/\r?\n/));
        else if(Array.isArray(item?.value)) items.push(...textItems(item.value));
        else if(item && 'value' in item) items.push(...textItems([item.value]));
    }
    return {type:'list', itemType:'text', value:items};
}

function move(items, index, offset) {
    const target = index + offset;
    if(index < 0 || target < 0 || index >= items.length || target >= items.length) return items;
    const next = [...items];
    [next[index], next[target]] = [next[target], next[index]];
    return next;
}

export async function activate(host) {
    host.registerNode({
        type:'list',
        title:'List',
        category:'Data',
        icon:'list',
        inputs:[{id:'input', label:'Items', type:'any'}],
        outputs:[{id:'list', label:'List', type:'list'}],
        create:() => ({items:[]}),
        render:({node}) => {
            const items = textItems(node.items);
            const rows = items.map((item, index) => `
                <div class="list-item" data-index="${index}">
                    <input class="list-item-value" type="text" value="${escapeAttribute(item)}" aria-label="Item ${index + 1}">
                    <button class="list-item-up" type="button" title="Move up" ${index === 0 ? 'disabled' : ''}>↑</button>
                    <button class="list-item-down" type="button" title="Move down" ${index === items.length - 1 ? 'disabled' : ''}>↓</button>
                    <button class="list-item-delete" type="button" title="Delete">×</button>
                </div>`).join('');
            return `<div class="list-fields">
                <div class="list-items">${rows || '<div class="list-empty">Empty List</div>'}</div>
                <button class="list-add-item" type="button">Add item</button>
            </div>`;
        },
        bindUI:({element, node}) => {
            const current = () => textItems(host.getNode?.(node.id)?.items ?? node.items);
            element.querySelector('.list-add-item')?.addEventListener('click', () => {
                host.updateNode?.(node.id, {items:[...current(), '']});
            });
            for(const row of element.querySelectorAll('.list-item')) {
                const index = Number(row.dataset.index);
                row.querySelector('.list-item-value')?.addEventListener('input', event => {
                    const items = current();
                    items[index] = event.target.value;
                    host.updateNode?.(node.id, {items}, {render:false});
                });
                row.querySelector('.list-item-delete')?.addEventListener('click', () => {
                    host.updateNode?.(node.id, {items:current().filter((_, itemIndex) => itemIndex !== index)});
                });
                row.querySelector('.list-item-up')?.addEventListener('click', () => {
                    host.updateNode?.(node.id, {items:move(current(), index, -1)});
                });
                row.querySelector('.list-item-down')?.addEventListener('click', () => {
                    host.updateNode?.(node.id, {items:move(current(), index, 1)});
                });
            }
        },
        execute:async ({node, inputs}) => ({
            outputs:{list:[listFromInputs(inputs) || {type:'list', itemType:'text', value:textItems(node.items)}]},
            flow:{continue:['list']},
            repeat:[],
        }),
        serialize:node => ({items:textItems(node.items)}),
        deserialize:data => ({items:textItems(data?.items)}),
    });
}
