export async function activate(host) {
    host.registerToolbarItem({
        id:'workspace',
        label:'Yanwo UI',
        title:'Yanwo UI workspace presentation',
        onClick:() => host.toast?.('Yanwo UI workspace presentation is active'),
    });
}
