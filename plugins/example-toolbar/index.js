export async function activate(host) {
    host.registerToolbarItem({
        id:'check',
        label:'Plugin Check',
        title:'Verify the example UI plugin',
        onClick:() => host.toast?.('Example toolbar plugin is active'),
    });
}
