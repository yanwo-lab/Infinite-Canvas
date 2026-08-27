function collectionValue(inputs) {
    const value = (Array.isArray(inputs?.collection) ? inputs.collection : [])
        .find(candidate => candidate?.type === 'list' && Array.isArray(candidate.value));
    return value || {type:'list', itemType:'any', value:[]};
}

export async function activate(host) {
    host.registerNode({
        type:'for-each',
        title:'For Each',
        category:'Flow',
        icon:'repeat-2',
        inputs:[{id:'collection', label:'Collection', type:'list'}],
        outputs:[
            {id:'item', label:'Item', type:'any'},
            {id:'index', label:'Index', type:'number'},
        ],
        create:() => ({}),
        render:() => `<div class="for-each-fields">
            <strong>For each item</strong>
            <span>Runs the connected branch once per collection item.</span>
        </div>`,
        execute:async ({inputs}) => {
            const collection = collectionValue(inputs);
            const length = collection.value.length;
            return {
                outputs:{},
                flow:{continue:['item', 'index']},
                repeat:collection.value.map((value, index) => ({
                    key:String(index),
                    outputs:{
                        item:[{type:collection.itemType || 'any', value}],
                        index:[{type:'number', value:index}],
                    },
                    context:{index, length, first:index === 0, last:index === length - 1},
                })),
                meta:{repeat:true},
            };
        },
        serialize:() => ({}),
        deserialize:() => ({}),
    });
}
