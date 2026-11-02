"""Tests for the trend-research flows. Run: python3 -m unittest discover -s tools/tests"""
import json
import unittest
import xml.etree.ElementTree as ET

from flowtest import built_text, find_action, load_built, params, path_to

PROCESS = "Workflows/TRProcessDocuments-58BCA39F-6F0F-4947-BA05-D2291EA1E08D.json"
PUBLIC = "/SourceUploads/PublicData/"


def dumps(node):
    return json.dumps(node)


class ProcessDocumentsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = load_built("en", PROCESS)
        cls.definition = cls.doc["properties"]["definition"]
        cls.trigger = next(iter(cls.definition["triggers"].values()))

    def test_trigger_uses_env_vars(self):
        self.assertEqual("When_a_file_is_created_or_modified", next(iter(self.definition["triggers"])))
        p = self.trigger["inputs"]["parameters"]
        self.assertEqual("@parameters('Site URL (tr_SiteURL)')", p["dataset"])
        self.assertEqual("@parameters('Source Uploads library (tr_SourceUploadsLibrary)')", p["table"])
        self.assertEqual("GetOnUpdatedFileItems", self.trigger["inputs"]["host"]["operationId"])

    def test_trigger_single_concurrency(self):
        self.assertEqual(1, self.trigger["runtimeConfiguration"]["concurrency"]["runs"])
        self.assertIn("splitOn", self.trigger)

    def test_only_public_paths_are_read(self):
        for name in ("Get_Upload_Source", "Get_Upload_Content"):
            self.assertEqual("If_Public_Path", path_to(self.doc, name)[0], name)
        expression = dumps(find_action(self.doc, "If_Public_Path")["expression"])
        self.assertIn("startsWith", expression)
        self.assertIn(PUBLIC, expression)
        self.assertEqual([], path_to(self.doc, "If_Public_Path"))

    def test_unmatched_folder_stops_before_evidence(self):
        trail = path_to(self.doc, "Create_Upload_Evidence")
        self.assertTrue(any(t == "If_Source_Found" for t in trail), trail)
        self.assertTrue(any(t == "If_New_Upload" for t in trail), trail)
        self.assertEqual({}, find_action(self.doc, "If_Source_Found")["else"]["actions"])
        self.assertEqual({}, find_action(self.doc, "If_New_Upload")["else"]["actions"])

    def test_source_path_filter_escapes_quotes(self):
        flt = params(self.doc, "Get_Upload_Source")["$filter"]
        self.assertIn("SourcePath eq '", flt)
        self.assertIn("field_2 eq 'Upload'", flt)
        self.assertIn("field_3 eq 1", flt)
        self.assertIn("replace(outputs('Build_Source_Path'), '''', '''''')", flt)
        self.assertEqual("1", str(params(self.doc, "Get_Upload_Source")["$top"]))

    def test_dedupe_uses_item_id(self):
        key = find_action(self.doc, "Build_ItemKey")["inputs"]
        text = dumps(key)
        self.assertIn("body/ID", text)
        self.assertIn("|", text)
        for bad in ("{Name}", "FilenameWithExtension", "body/Name"):
            self.assertNotIn(bad, text)
        self.assertIn("If_New_Upload", path_to(self.doc, "Get_Upload_Content"))
        self.assertIn("field_3 eq '", params(self.doc, "Check_Upload_SourceItem_Exists")["$filter"])

    def test_text_gate_case_insensitive_and_sized(self):
        text = dumps(find_action(self.doc, "If_Text_File")["expression"])
        self.assertIn("toLower", text)
        for ext in ("txt", "md", "csv", "html", "htm"):
            self.assertIn(f'"{ext}"', text)
        self.assertEqual(5, text.count("equals"))
        for other in ("pdf", "docx", "json", "xml"):
            self.assertNotIn(f'"{other}"', text)
        self.assertIn("tr_MaxUploadBytes", text)
        self.assertIn("Size", text)

    def test_unsupported_type_is_metadata_only(self):
        gate = find_action(self.doc, "If_Text_File")
        self.assertEqual("MetadataOnly", find_action(self.doc, "Set_ContentStatus_MetadataOnly")["inputs"]["value"])
        self.assertIn("Set_ContentStatus_MetadataOnly", gate["else"]["actions"])
        self.assertEqual("If_Text_File/else", path_to(self.doc, "Set_ContentStatus_MetadataOnly")[-1])
        self.assertNotIn("Get_Upload_Content", gate["else"]["actions"])
        self.assertEqual("@variables('ContentStatus')", params(self.doc, "Create_Upload_SourceItem")["item/field_8"])
        init = find_action(self.doc, "Initialize_ContentStatus")["inputs"]["variables"][0]
        self.assertEqual("FullText", init["value"])

    def test_get_content_not_inferred(self):
        self.assertIs(False, params(self.doc, "Get_Upload_Content")["inferContentType"])
        self.assertIn("base64ToString", dumps(find_action(self.doc, "Set_Text")["inputs"]))

    def test_evidence_name_uses_item_id(self):
        p = params(self.doc, "Create_Upload_Evidence")
        self.assertEqual("/Evidence", p["folderPath"])
        self.assertEqual("upload-@{triggerOutputs()?['body/ID']}.txt", p["name"])
        self.assertNotIn("Name", p["name"])

    def test_source_item_ready(self):
        p = params(self.doc, "Create_Upload_SourceItem")
        self.assertEqual("Ready", p["item/field_9"])
        self.assertEqual("@triggerOutputs()?['body/ID']", p["item/field_2"])
        self.assertNotIn("item/PublishedAt", p)

    def test_process_documents_localized(self):
        for locale, name in (("en", "TR Process Documents"), ("es", "VT Procesar Documentos")):
            xml = ET.fromstring(built_text(locale, "customizations.xml").lstrip("﻿"))
            self.assertIn(name, [w.get("Name") for w in xml.iter("Workflow")])
        self.assertIn('Name="VT Procesar Documentos"', built_text("es", "customizations.xml"))


if __name__ == "__main__":
    unittest.main()
