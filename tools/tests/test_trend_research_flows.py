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

CLASSIFY = "Workflows/TRClassifyItems-F73F937F-667A-8EDC-33BF-30CDDB0276B6.json"
ALERT_CODES = ["CompetitorLaunch", "RegulatoryAlert", "NewTechnology"]
OBJECTIVE_CODES = ["Anticipate", "MinimizeRisks", "Compare", "Innovate", "Cooperate"]


class ClassifierV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = load_built("en", CLASSIFY)

    def _schema(self):
        agent = params(self.doc, "Classify_TR_Signal")["body/definition"]
        return json.loads(agent["entity"]["configuration"]["agentSettings"]["output"]["schema"])

    def test_prompt_v3_has_product_dimension(self):
        msg = params(self.doc, "Classify_TR_Signal")["body/message"]
        self.assertIn("Product: @{items('Loop_2')?['Product']}", msg)
        self.assertIn("Dimension: @{items('Loop_2')?['Dimension']}", msg)
        schema = self._schema()
        for name in ("AlertTags", "Objectives"):
            self.assertEqual({"type": "array", "items": {"type": "string"}}, schema["properties"][name])
            self.assertIn(name, schema["required"])
        for code in ALERT_CODES + OBJECTIVE_CODES:
            self.assertIn(code, msg)

    def test_alert_tags_filtered_to_allowed(self):
        for action, codes, prop in (("Filter_AlertTags", ALERT_CODES, "AlertTags"),
                                    ("Filter_Objectives", OBJECTIVE_CODES, "Objectives")):
            f = find_action(self.doc, action)
            self.assertEqual("Query", f["type"])
            self.assertEqual("@coalesce(body('Classify_TR_Signal')?['structuredOutput/%s'], json('[]'))" % prop,
                             f["inputs"]["from"])
            self.assertEqual("@contains(createArray(%s), item())" % ", ".join("'%s'" % c for c in codes),
                             f["inputs"]["where"])
            self.assertEqual({"Classify_TR_Signal": ["Succeeded"]} if action == "Filter_AlertTags"
                             else {"Filter_AlertTags": ["Succeeded"]}, f["runAfter"])
        p = params(self.doc, "Create_Signal")
        self.assertEqual("@body('Filter_AlertTags')", p["item/AlertTags"])
        self.assertEqual("@body('Filter_Objectives')", p["item/Objectives"])
        for prop in ("item/AlertTags", "item/Objectives"):
            self.assertNotIn("structuredOutput", p[prop])  # raw model output is never written as-is
        self.assertIn("Filter_Objectives", find_action(self.doc, "Create_Signal")["runAfter"])

    def test_invalid_tags_route_to_review(self):
        p = params(self.doc, "Create_Signal")
        status = p["item/field_11"]
        self.assertIn("NeedsReview", status)
        for raw, filt in (("AlertTags", "Filter_AlertTags"), ("Objectives", "Filter_Objectives")):
            self.assertIn("structuredOutput/%s" % raw, status)
            self.assertIn("body('%s')" % filt, status)
        self.assertIn("Invalid tags:", p["item/field_10"])
        self.assertIn("Supporting evidence:", p["item/field_10"])
        # a Rejected/Monitor/Digest outcome is still computed when tags are valid
        for v in ("Rejected", "Monitor", "Digest"):
            self.assertIn(v, status)

    def test_analysis_key_uses_prompt_v3(self):
        key = find_action(self.doc, "Build_AnalysisKey")["inputs"]["value"]
        self.assertTrue(key.endswith("|3"), key)
        self.assertEqual(3, params(self.doc, "Create_Signal")["item/field_5"])

    def test_failed_brief_not_marked_classified(self):
        a = find_action(self.doc, "Mark_SourceItem_Classified")
        # Mark waits for Filter_Failed_Briefs, which itself runs after Loop_2 whatever its outcome
        self.assertEqual({"Filter_Failed_Briefs": ["Succeeded"]}, a["runAfter"])
        status = a["inputs"]["parameters"]["item/field_9"]
        self.assertIn("'Failed'", status)
        self.assertIn("'Classified'", status)
        self.assertIn("Filter_Failed_Briefs", status)
        f = find_action(self.doc, "Filter_Failed_Briefs")
        self.assertIn("result('Loop_2')", f["inputs"]["from"])
        self.assertIn("'Failed'", f["inputs"]["where"])
        self.assertEqual({"Loop_2": ["Succeeded", "Failed"]}, f["runAfter"])

    def test_loop_2_stays_sequential(self):
        self.assertEqual(1, find_action(self.doc, "Loop_2")["runtimeConfiguration"]["concurrency"]["repetitions"])


DIGEST = "Workflows/TRWeeklyDigest-D630FC9C-EA1F-8FBE-B44A-2DFEC38D631C.json"
OBJ_ES = ["Anticipar", "Minimizar riesgos", "Comparar", "Innovar", "Cooperar"]


class DigestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = load_built("en", DIGEST)

    def test_digest_publication_metadata(self):
        p = params(self.doc, "Create_Publication_Record")
        self.assertEqual("@items('Loop_Brief')?['ID']", p["item/BriefId"])
        self.assertEqual("@items('Loop_Brief')?['Product']", p["item/Product"])
        self.assertEqual("@items('Loop_Brief')?['Dimension']?['Value']", p["item/Dimension"])
        self.assertEqual("Digest", p["item/PublicationType"])
        header = find_action(self.doc, "Digest_HTML")["inputs"]["value"]
        self.assertIn("items('Loop_Brief')?['Product']", header)
        self.assertIn("items('Loop_Brief')?['Dimension']?['Value']", header)
        self.assertIn("items('Loop_Brief')?['field_1']", header)
        self.assertIn("variables('WindowEndDate')", header)
        self.assertIn("equals(items('Loop_Brief')?['Dimension']?['Value'], 'Market')", header)
        self.assertIn("Market", json.dumps(load_built("es", DIGEST)))

    def test_digest_has_five_objective_sections_in_order(self):
        for locale, names in (("es", OBJ_ES),):
            doc = load_built(locale, DIGEST)
            text = json.dumps(doc)
            pos = [text.index("<h2>%s</h2>" % n) for n in names]
            self.assertEqual(sorted(pos), pos)
        for code in OBJECTIVE_CODES:
            f = find_action(self.doc, "Filter_Digest_" + code)
            self.assertEqual("Query", f["type"])
            self.assertEqual("@coalesce(body('Get_Digest_Signals')?['value'], json('[]'))", f["inputs"]["from"])
            self.assertIn("'\"Value\":\"%s\"'" % code, f["inputs"]["where"])
            loop = find_action(self.doc, "Loop_" + code)
            self.assertEqual("Foreach", loop["type"])
            self.assertEqual("@body('Filter_Digest_%s')" % code, loop["foreach"])
            self.assertEqual(1, loop["runtimeConfiguration"]["concurrency"]["repetitions"])
        self.assertEqual(5, len([1 for c in OBJECTIVE_CODES if find_action(self.doc, "Loop_" + c)]))

    def test_empty_objective_prints_no_findings(self):
        for code in OBJECTIVE_CODES:
            h = find_action(self.doc, "Heading_" + code)["inputs"]["value"]
            self.assertIn("empty(body('Filter_Digest_%s'))" % code, h)
            self.assertIn("No findings", h)
        self.assertIn("Sin hallazgos", json.dumps(load_built("es", DIGEST)))

    def test_alert_tags_caption_and_single_template(self):
        tpl = find_action(self.doc, "Initialize_variable_SignalTemplate")["inputs"]["variables"][0]["value"]
        self.assertIn("[[TAGS]]", tpl)
        text = json.dumps(self.doc)
        self.assertEqual(1, text.count("Open original source"))  # signal HTML lives in one template only
        self.assertIn("Alert tags", text)
        self.assertNotIn("alert sent", text.lower())
        self.assertNotIn("notified", text.lower())


BUSINESS_CASE = "Workflows/TRBusinessCase-9373450F-FA1E-44C2-ACE2-2D86CA9249C7.json"
REQUEST = "body('Get_Request')"
REQUIRED_REQUEST_FIELDS = ["Title", "Product", "DecisionQuestion", "Geographies", "TimeHorizon", "Alternatives",
                           "StrategicObjectives", "InputPublicationIds", "ReviewerEmail", "AudienceKey"]


class BusinessCaseValidateClaimTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = load_built("en", BUSINESS_CASE)
        cls.definition = cls.doc["properties"]["definition"]
        cls.trigger = cls.definition["triggers"]["When_a_request_is_submitted"]

    def assert_failed_write(self, name):
        """The owning run writes Failed with a MERGE; IF-MATCH * because it already claimed the item."""
        a = find_action(self.doc, name)
        self.assertEqual("HttpRequest", a["inputs"]["host"]["operationId"])
        p = a["inputs"]["parameters"]
        claim = params(self.doc, "Claim_Request")
        self.assertEqual("POST", p["parameters/method"])
        self.assertEqual(claim["parameters/uri"], p["parameters/uri"])
        self.assertEqual("*", p["parameters/headers"]["IF-MATCH"])
        self.assertEqual("MERGE", p["parameters/headers"]["X-HTTP-Method"])
        for locale in ("en", "es"):
            body = json.loads(params(load_built(locale, BUSINESS_CASE), name)["parameters/body"])
            self.assertEqual(["Status", "LastError"], list(body))
            self.assertEqual("Failed", body["Status"])

    def _branch(self, condition, branch):
        a = find_action(self.doc, condition)
        return a["actions"] if branch == "yes" else a["else"]["actions"]

    def test_trigger_fires_only_on_submitted(self):
        self.assertEqual(["When_a_request_is_submitted"], list(self.definition["triggers"]))
        self.assertEqual("GetOnUpdatedItems", self.trigger["inputs"]["host"]["operationId"])
        p = self.trigger["inputs"]["parameters"]
        self.assertEqual("@parameters('Site URL (tr_SiteURL)')", p["dataset"])
        table = p["table"][len("@parameters('"):-2]
        self.assertEqual("tr_BusinessCaseRequestsList", self.definition["parameters"][table]["metadata"]["schemaName"])
        self.assertEqual("@equals(triggerOutputs()?['body/Status/Value'], 'Submitted')",
                         self.trigger["conditions"][0]["expression"])
        self.assertEqual(1, len(self.trigger["conditions"]))
        # the ETag claim makes concurrent runs safe; the cap is a throughput limit only
        self.assertEqual(25, self.trigger["runtimeConfiguration"]["concurrency"]["runs"])
        self.assertIn("splitOn", self.trigger)

    def test_request_reread_and_validated(self):
        get = find_action(self.doc, "Get_Request")
        self.assertEqual("GetItem", get["inputs"]["host"]["operationId"])
        self.assertEqual("@triggerOutputs()?['body/ID']", get["inputs"]["parameters"]["id"])
        expression = dumps(find_action(self.doc, "If_Request_Valid")["expression"])
        self.assertIn("%s?['Status']?['Value']" % REQUEST, expression)
        self.assertIn('"Submitted"', expression)
        for field in REQUIRED_REQUEST_FIELDS:
            self.assertIn("trim(coalesce(%s?['%s'], ''))" % (REQUEST, field), expression, field)
        version = "coalesce(%s?['Version'], 0)" % REQUEST
        self.assertIn('{"greaterOrEquals": ["@%s", 1]}' % version, expression)
        self.assertIn('{"lessOrEquals": ["@mod(%s, 1)", 0]}' % version, expression)
        # membership in an array, never a substring match on the raw setting
        self.assertIn("\"contains\": [\"@body('Select_Approved_Reviewers')\", "
                      "\"@toLower(trim(coalesce(%s?['ReviewerEmail'], '')))\"]" % REQUEST, expression)
        self.assertIn("\"contains\": [\"@body('Select_Approved_Audiences')\", "
                      "\"@trim(coalesce(%s?['AudienceKey'], ''))\"]" % REQUEST, expression)
        for select, schema in (("Select_Approved_Reviewers", "tr_ApprovedReviewers"),
                               ("Select_Approved_Audiences", "tr_ApprovedAudiences")):
            a = find_action(self.doc, select)
            self.assertEqual("Select", a["type"])
            name = next(k for k, v in self.definition["parameters"].items()
                        if v.get("metadata", {}).get("schemaName") == schema)
            self.assertEqual("@split(coalesce(parameters('%s'), ''), ';')" % name, a["inputs"]["from"])
            self.assertEqual([], path_to(self.doc, select))

    def test_invalid_request_leaves_status_unchanged(self):
        actions = self._branch("If_Request_Valid", "else")
        self.assertEqual(["Terminate_Invalid_Request"], list(actions))
        t = actions["Terminate_Invalid_Request"]
        self.assertEqual("Terminate", t["type"])
        self.assertEqual("Failed", t["inputs"]["runStatus"])
        self.assertTrue(t["inputs"]["runError"]["message"])
        es = find_action(load_built("es", BUSINESS_CASE), "Terminate_Invalid_Request")
        self.assertNotEqual(t["inputs"]["runError"]["message"], es["inputs"]["runError"]["message"])

    def test_existing_key_skips_ai(self):
        self.assertEqual("businesscase|@{%s?['ID']}|v@{%s?['Version']}" % (REQUEST, REQUEST),
                         find_action(self.doc, "Build_Publication_Key")["inputs"])
        p = params(self.doc, "Get_Existing_Publication")
        self.assertEqual("field_1 eq '@{outputs('Build_Publication_Key')}'", p["$filter"])
        self.assertEqual("1", str(p["$top"]))
        self.assertIn("Publications", self.definition["parameters"][p["table"][len("@parameters('"):-2]]
                      ["metadata"]["schemaName"])
        gate = find_action(self.doc, "If_No_Existing_Publication")
        self.assertEqual({"and": [{"empty": ["@body('Get_Existing_Publication')?['value']"]}]}, gate["expression"])
        trail = path_to(self.doc, "Generate_Case")
        self.assertIn("If_No_Existing_Publication", trail)
        self.assertNotIn("If_No_Existing_Publication/else", trail)
        self.assertIn("If_No_Existing_Publication", path_to(self.doc, "Claim_Request"))
        found = self._branch("If_No_Existing_Publication", "else")
        self.assertEqual(["Terminate_Existing_Publication"], list(found))
        self.assertEqual("Succeeded", found["Terminate_Existing_Publication"]["inputs"]["runStatus"])

    def test_claim_uses_etag(self):
        claim = find_action(self.doc, "Claim_Request")
        self.assertEqual("HttpRequest", claim["inputs"]["host"]["operationId"])
        p = claim["inputs"]["parameters"]
        self.assertEqual("POST", p["parameters/method"])
        headers = p["parameters/headers"]
        self.assertEqual("@{%s?['@odata.etag']}" % REQUEST, headers["IF-MATCH"])
        self.assertEqual("MERGE", headers["X-HTTP-Method"])
        list_param = next(k for k, v in self.definition["parameters"].items()
                          if v.get("metadata", {}).get("schemaName") == "tr_BusinessCaseRequestsList")
        self.assertEqual("_api/web/lists/GetByTitle('@{parameters('%s')}')/items(@{%s?['ID']})"
                         % (list_param, REQUEST), p["parameters/uri"])
        self.assertEqual({"Status": "Generating"}, json.loads(p["parameters/body"]))
        self.assertEqual(["If_Request_Valid", "If_No_Existing_Publication"], path_to(self.doc, "Claim_Request"))
        # a lost claim (412) cancels; any other claim failure stops the run; only a won claim continues
        conflict = find_action(self.doc, "If_Claim_Conflict")
        self.assertEqual({"Claim_Request": ["Failed", "TimedOut"]}, conflict["runAfter"])
        self.assertEqual({"and": [{"equals": ["@outputs('Claim_Request')?['statusCode']", 412]}]},
                         conflict["expression"])
        self.assertEqual(["Terminate_Claim_Conflict"], list(conflict["actions"]))
        self.assertEqual({"runStatus": "Cancelled"}, conflict["actions"]["Terminate_Claim_Conflict"]["inputs"])
        self.assertEqual(["Terminate_Claim_Failed"], list(conflict["else"]["actions"]))
        self.assertEqual("Failed", conflict["else"]["actions"]["Terminate_Claim_Failed"]["inputs"]["runStatus"])
        # a retried 5xx after an applied write would get 412 and leave the item stuck in Generating
        self.assertEqual({"type": "none"}, claim["inputs"]["retryPolicy"])
        self.assertEqual({"Claim_Request": ["Succeeded"]}, find_action(self.doc, "Split_Input_Ids")["runAfter"])

    def test_input_ids_bounds(self):
        split = find_action(self.doc, "Split_Input_Ids")
        self.assertEqual("@split(coalesce(%s?['InputPublicationIds'], ''), ',')" % REQUEST, split["inputs"]["from"])
        self.assertEqual("@trim(item())", split["inputs"]["select"])
        parse = find_action(self.doc, "Parse_Input_Ids")
        self.assertEqual("Query", parse["type"])
        self.assertEqual("@body('Split_Input_Ids')", parse["inputs"]["from"])
        self.assertEqual("@not(empty(item()))", parse["inputs"]["where"])
        # int() throws on a non-number; the Scope catches it and InputIdsValid stays false
        self.assertEqual(["Check_Input_Ids"], path_to(self.doc, "Filter_Invalid_Ids")[-1:])
        self.assertEqual("Scope", find_action(self.doc, "Check_Input_Ids")["type"])
        where = find_action(self.doc, "Filter_Invalid_Ids")["inputs"]["where"]
        self.assertEqual("@not(and(equals(string(int(item())), item()), greater(int(item()), 0)))", where)
        ids = "body('Parse_Input_Ids')"
        value = find_action(self.doc, "Set_InputIdsValid")["inputs"]["value"]
        self.assertEqual("@and(empty(body('Filter_Invalid_Ids')), greaterOrEquals(length(%s), 1), "
                         "lessOrEquals(length(%s), 5), equals(length(union(%s, %s)), length(%s)))"
                         % (ids, ids, ids, ids, ids), value)
        init = find_action(self.doc, "Initialize_InputIdsValid")["inputs"]["variables"][0]
        self.assertIs(False, init["value"])
        gate = find_action(self.doc, "If_Input_Ids_Valid")
        self.assertEqual({"Check_Input_Ids": ["Succeeded", "Failed", "TimedOut"]}, gate["runAfter"])
        self.assertEqual({"and": [{"equals": ["@variables('InputIdsValid')", True]}]}, gate["expression"])
        failed = gate["else"]["actions"]
        self.assertEqual(["Set_Failed_Input_Ids", "Terminate_Invalid_Input_Ids"], list(failed))
        self.assert_failed_write("Set_Failed_Input_Ids")
        self.assertEqual({"Set_Failed_Input_Ids": ["Succeeded", "Failed", "TimedOut"]},
                         failed["Terminate_Invalid_Input_Ids"]["runAfter"])
        self.assertEqual("Failed", failed["Terminate_Invalid_Input_Ids"]["inputs"]["runStatus"])
        self.assertIn("If_Input_Ids_Valid", path_to(self.doc, "Generate_Case"))
        self.assertNotIn("If_Input_Ids_Valid/else", path_to(self.doc, "Generate_Case"))

    def test_wrong_product_fails_before_ai(self):
        self.assertEqual({"Validate_Each_Digest": ["Succeeded"]}, find_action(self.doc, "Generate_Case")["runAfter"])
        loop = find_action(self.doc, "Validate_Each_Digest")
        self.assertEqual("Foreach", loop["type"])
        self.assertEqual("@body('Parse_Input_Ids')", loop["foreach"])
        get = params(self.doc, "Get_Digest")
        self.assertEqual("@int(items('Validate_Each_Digest'))", get["id"])
        self.assertIn("tr_PublicationsList", self.definition["parameters"][get["table"][len("@parameters('"):-2]]
                      ["metadata"]["schemaName"])
        check = find_action(self.doc, "If_Digest_Invalid")
        self.assertEqual({"or": [
            {"not": {"equals": ["@body('Get_Digest')?['PublicationType']?['Value']", "Digest"]}},
            {"not": {"equals": ["@trim(coalesce(body('Get_Digest')?['Product'], ''))",
                                "@trim(coalesce(%s?['Product'], ''))" % REQUEST]}},
            {"empty": ["@trim(coalesce(body('Get_Digest')?['field_3'], ''))"]},
        ]}, check["expression"])
        self.assertEqual({"Get_Digest": ["Succeeded"]}, check["runAfter"])
        self.assertIn("Reject_Invalid_Digest", check["actions"])
        self.assertEqual({}, check["else"]["actions"])
        handler = find_action(self.doc, "Set_Failed_Digests")
        self.assertEqual({"Validate_Each_Digest": ["Failed", "TimedOut"]}, handler["runAfter"])
        self.assert_failed_write("Set_Failed_Digests")
        self.assertEqual({"Set_Failed_Digests": ["Succeeded", "Failed", "TimedOut"]},
                         find_action(self.doc, "Terminate_Invalid_Digest")["runAfter"])
        self.assertEqual("Failed", find_action(self.doc, "Terminate_Invalid_Digest")["inputs"]["runStatus"])

    def test_failure_messages_are_safe_and_localized(self):
        es = load_built("es", BUSINESS_CASE)
        for name in ("Set_Failed_Input_Ids", "Set_Failed_Digests"):
            message = json.loads(params(self.doc, name)["parameters/body"])["LastError"]
            self.assertTrue(message)
            self.assertNotIn("@", message)  # a fixed message: no request, digest or response content
            self.assertNotEqual(message, json.loads(params(es, name)["parameters/body"])["LastError"])

    def test_business_case_localized(self):
        for locale, name in (("en", "TR Business Case"), ("es", "VT Caso de Negocio")):
            xml = ET.fromstring(built_text(locale, "customizations.xml").lstrip("﻿"))
            self.assertIn(name, [w.get("Name") for w in xml.iter("Workflow")])


if __name__ == "__main__":
    unittest.main()
