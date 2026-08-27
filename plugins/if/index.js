function conditionValue(node, inputs) {
    const upstream = (Array.isArray(inputs?.condition) ? inputs.condition : [])
        .find(value => value?.type === 'boolean' && typeof value.value === 'boolean');
    if(upstream) return {value:upstream.value, source:'input'};
    return {value:node?.condition === true, source:'node'};
}

export async function activate(host) {
    host.registerNode({
        type:'if',
        title:'IF',
        category:'Flow',
        icon:'git-branch',
        inputs:[{id:'condition', label:'Condition', type:'boolean'}],
        outputs:[
            {id:'true', label:'True', type:'any'},
            {id:'false', label:'False', type:'any'},
        ],
        create:() => ({condition:false}),
        render:({node}) => `<label class="if-condition-field">
            <input class="if-condition-input" type="checkbox" ${node.condition === true ? 'checked' : ''}>
            <span>Condition when no input is connected</span>
        </label>`,
        bindUI:({element, node}) => {
            element.querySelector('.if-condition-input')?.addEventListener('change', event => {
                host.updateNode?.(node.id, {condition:event.target.checked === true}, {render:false});
            });
        },
        execute:async ({node, inputs}) => {
            const condition = conditionValue(node, inputs);
            const selected = condition.value ? 'true' : 'false';
            return {
                outputs:{
                    true:condition.value ? [{type:'boolean', value:true}] : [],
                    false:condition.value ? [] : [{type:'boolean', value:false}],
                },
                flow:{continue:[selected]},
                repeat:[],
                meta:{conditionSource:condition.source},
            };
        },
        serialize:node => ({condition:node?.condition === true}),
        deserialize:data => ({condition:data?.condition === true}),
    });
}
