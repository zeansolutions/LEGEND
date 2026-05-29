# -*- coding: utf-8 -*-
"""
run_core_tests.py - Unittest Suite for LEGEND Core Utilities and Semantic Modules.
Verifies all functionality in core_utils.py.
"""

import unittest
import unittest
import os
import sqlite3
import json
import networkx as nx
import core_utils


class TestCoreUtils(unittest.TestCase):
    
    def setUp(self):
        # Setup clean temporary SQLite database for testing connection manager
        self.db_path = "test_ontology.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
            
    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
            
    def test_database_connection_manager(self):
        """Verifies database context manager handles connections, commits and rollbacks safely."""
        with core_utils.get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, value TEXT)")
            cursor.execute("INSERT INTO test_table (value) VALUES ('hello')")
            
        # Verify transaction committed
        with core_utils.get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM test_table")
            row = cursor.fetchone()
            self.assertEqual(row[0], "hello")
            
        # Verify rollback on exception
        try:
            with core_utils.get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO test_table (value) VALUES ('world')")
                raise ValueError("Simulated Exception")
        except ValueError:
            pass
            
        # Should only have 'hello'
        with core_utils.get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM test_table")
            count = cursor.fetchone()[0]
            self.assertEqual(count, 1)

    def test_arabic_normalization(self):
        """Tests that various Arabic dialectal orthography, diacritics and letters are unified correctly."""
        inputs = [
            ("أَلْقَاهِرَةُ", "القاهره"),
            ("إِنْسَان", "انسان"),
            ("حَيَاةٌ", "حياه"),
            ("شَجَرَةِ", "شجره"),
            ("مستشفى", "مستشفي"),
            ("الْعِلْمُ_نُورٌ", "العلم نور")
        ]
        for inp, expected in inputs:
            normalized = core_utils.normalize_arabic(inp, remove_separators=True)
            self.assertEqual(normalized, expected)

    def test_arabic_stemmer(self):
        """Tests that prefix and suffix morphological variations are successfully stripped down to core stems."""
        word = "والشمس"
        stems = core_utils.stem_arabic(word)
        self.assertTrue("شمس" in stems or "شمس" in [s.replace(" ", "") for s in stems])
        
        word2 = "كتابها"
        stems2 = core_utils.stem_arabic(word2)
        self.assertTrue("كتاب" in stems2)

    def test_character_similarity(self):
        """Tests standard character-level Jaccard similarity score logic."""
        sim1 = core_utils.char_similarity("كتاب", "الكتّاب")
        sim2 = core_utils.char_similarity("قلم", "دفتر")
        self.assertTrue(sim1 > 0.6)
        self.assertTrue(sim2 < 0.2)

    def test_semantic_web_exporters(self):
        """Validates standard RDF/XML, Turtle and JSON-LD syntax converters."""
        g = nx.DiGraph()
        g.add_node("الأسد", type="concept", super_type="حيوان")
        g.add_edge("الأسد", "الغابة", relation="يعيش_في", confidence=0.95)
        
        # Test RDF XML
        rdf_xml = core_utils.export_to_rdf(g, format="xml")
        self.assertTrue('xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"' in rdf_xml)
        self.assertTrue("http://legend.ai/ontology#الأسد" in rdf_xml)
        
        # Test Turtle
        rdf_ttl = core_utils.export_to_rdf(g, format="turtle")
        self.assertTrue("legend:الأسد a rdfs:Class ;" in rdf_ttl)
        self.assertTrue("legend:الأسد legend:يعيش_في legend:الغابة ;" in rdf_ttl)
        
        # Test JSON-LD
        json_ld = core_utils.export_to_json_ld(g)
        parsed = json.loads(json_ld)
        self.assertEqual(parsed["@graph"][0]["name"], "الأسد")

    def test_lite_similarity_search(self):
        """Tests the lightweight lexical and character Jaccard-vector similarity query matcher."""
        g = nx.DiGraph()
        g.add_node("مدرسة المتفوقين")
        g.add_node("قلم حبر أزرق")
        g.add_node("جامعة القاهرة")
        
        # Querying "مدرسة" should find "مدرسة المتفوقين"
        results = core_utils.search_similar_nodes(g, "مدرسة", threshold=0.3)
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0][0], "مدرسة المتفوقين")


    def test_temporal_filtering(self):
        """Tests filtering of historic or future temporal assertion triples."""
        triples = [
            ("أحمد", "يعيش_في", "القاهرة", 2010, 2020, 1.0),
            ("أحمد", "يعيش_في", "لندن", 2021, None, 1.0),
            ("أحمد", "ولد_في", "القاهرة", None, None, 1.0)
        ]
        
        # In 2015, Ahmad lives in Cairo, and was born in Cairo
        res_2015 = core_utils.filter_triples_by_time(triples, 2015)
        self.assertEqual(len(res_2015), 2)
        subjects_2015 = [t[2] for t in res_2015]
        self.assertTrue("القاهرة" in subjects_2015)
        
        # In 2025, Ahmad lives in London, and was born in Cairo
        res_2025 = core_utils.filter_triples_by_time(triples, 2025)
        self.assertEqual(len(res_2025), 2)
        subjects_2025 = [t[2] for t in res_2025]
        self.assertTrue("لندن" in subjects_2025)

    def test_predict_impact_chain(self):
        """Tests the causality impact prediction chain logic."""
        from cli.engine import ArabicReasoningEngine
        engine = ArabicReasoningEngine("test_ontology.db")
        # Populate mock causality graph
        engine.graph.clear()
        h1 = core_utils.normalize_arabic("ارتفاع درجة الحرارة")
        h2 = core_utils.normalize_arabic("ذوبان الجليد")
        h3 = core_utils.normalize_arabic("ارتفاع منسوب البحر")
        
        engine.graph.add_node(h1, type="concept")
        engine.graph.add_node(h2, type="concept")
        engine.graph.add_node(h3, type="concept")
        engine.graph.add_edge(h1, h2, relation="يؤدي_إلى", confidence=0.9)
        engine.graph.add_edge(h2, h3, relation="يسبب", confidence=0.8)
        
        logs = []
        chain = engine.predict_impact_chain("ارتفاع درجة الحرارة", logs)


        self.assertEqual(len(chain), 2)

        self.assertEqual(chain[0]["from"], h1)
        self.assertEqual(chain[0]["to"], h2)
        self.assertEqual(chain[0]["confidence"], 0.9)
        self.assertEqual(chain[1]["from"], h2)
        self.assertEqual(chain[1]["to"], h3)
        self.assertEqual(chain[1]["cumulative_confidence"], 0.72) # 0.9 * 0.8


if __name__ == "__main__":
    unittest.main()

