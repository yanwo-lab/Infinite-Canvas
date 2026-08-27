function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
}

export async function activate(host) {
    host.registerNode({
        type:'example-text',
        title:'Example Text',
        category:'Examples',
        icon:'type',
        inputs:[{id:'input', label:'Text', type:'text'}],
        outputs:[{id:'output', label:'Text', type:'text'}],
        create:() => ({text:'', output:''}),
        render:({node}) => `
            <div class="example-text-fields">
                <textarea class="example-text-input" placeholder="Text">${escapeHtml(node.text || '')}</textarea>
                <button class="example-text-preview" type="button">Preview</button>
                <output>${escapeHtml(node.output || '')}</output>
            </div>`,
        bindUI:({element, node}) => {
            const input = element.querySelector('.example-text-input');
            const button = element.querySelector('.example-text-preview');
            const update = patch => host.updateNode?.(node.id, patch);
            input?.addEventListener('input', event => host.updateNode?.(node.id, {text:event.target.value}, {render:false}));
            button?.addEventListener('click', () => update({output:`Example: ${input?.value || ''}`}));
        },
        execute:async ({node, inputs}) => {
            const upstream = inputs.input?.find(item => item?.type === 'text');
            const text = upstream ? String(upstream.value ?? '') : String(node.text || '');
            const value = `Example: ${text}`;
            host.updateNode?.(node.id, {output:value});
            return {outputs:{output:[{type:'text', value}]}, flow:{continue:['output']}, repeat:[]};
        },
        serialize:node => ({text:String(node.text || ''), output:String(node.output || '')}),
        deserialize:data => ({text:String(data?.text || ''), output:String(data?.output || '')}),
    });
}
