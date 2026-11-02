import unittest

from app.extraction.html_extractor import extract_html


class ExtractHtmlTests(unittest.TestCase):
    def test_script_is_dropped_from_text(self):
        html = "<script>alert(1)</script><p>Hola Acme</p>"

        self.assertEqual(extract_html(html, "text"), "Hola Acme")

    def test_styles_and_comments_are_dropped_from_markdown(self):
        html = "<style>p{}</style><!-- secret --><h1>Titulo</h1>"

        result = extract_html(html, "markdown")

        self.assertIn("# Titulo", result)
        self.assertNotIn("secret", result)
        self.assertNotIn("p{}", result)

    def test_hidden_elements_are_dropped(self):
        html = (
            '<div hidden>Oculto</div>'
            '<div style="display: none">Oculto2</div>'
            '<div aria-hidden="true">Oculto3</div>'
            '<p>Visible</p>'
        )

        self.assertEqual(extract_html(html, "text"), "Visible")

    def test_markdown_does_not_escape_underscores(self):
        # Final review F1: an escaped "_" breaks the match for a term or an email.
        html = "<p>juan_perez@acme.es Acme_Corp</p>"

        self.assertEqual(extract_html(html, "markdown"), "juan_perez@acme.es Acme_Corp")

    def test_noscript_and_template_are_dropped(self):
        html = "<noscript>Enable JS</noscript><template>Tpl</template><p>Texto</p>"

        self.assertEqual(extract_html(html, "text"), "Texto")


if __name__ == "__main__":
    unittest.main()
