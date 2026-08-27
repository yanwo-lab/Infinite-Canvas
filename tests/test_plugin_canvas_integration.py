import unittest
from pathlib import Path


class PluginCanvasIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path("static/js/smart-canvas.js").read_text(encoding="utf-8")

    def test_unknown_plugin_nodes_skip_builtin_media_normalization(self):
        self.assertIn("if(pluginHost?.isPluginNode(node)) return;", self.source)
        self.assertIn("!pluginHost?.isPluginNode(n) && n.jimengPending", self.source)
        self.assertIn("!pluginHost?.isPluginNode(node) && smartPendingTasks(node).length", self.source)

    def test_dragged_plugin_connections_keep_named_ports(self):
        self.assertIn("fromPortId", self.source)
        self.assertIn("toPortId", self.source)
        self.assertIn("data-port-id", self.source)


if __name__ == "__main__":
    unittest.main()
