"""Offline ingestion regression tests; retailer selectors are fixture-only."""

import unittest
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup

from database.validation import number, release_year, specifications
from scripts import load_historical_data as historical
from scripts import scrape_retailers as retailer
from scripts import update_prices
from scripts import migrate_recommendations as migration
from scrapers.retailer_scrapers.globalgolf_scraper import GlobalGolfScraper


class FakeDB:
    def __init__(self, cursor):
        self.cursor = cursor
        self.commits = 0
        self.rollbacks = 0
        self.sessions = 0

    @contextmanager
    def get_cursor(self):
        self.sessions += 1
        try:
            yield self.cursor
        except Exception:
            self.rollbacks += 1
            raise
        else:
            self.commits += 1


class ValidationTests(unittest.TestCase):
    def test_unknown_year_and_invalid_numbers(self):
        self.assertIsNone(release_year(None))
        for value in (True, float('nan'), float('inf'), -1, "free"):
            with self.assertRaises((ValueError, TypeError)):
                number(value)
        with self.assertRaises(ValueError):
            release_year(2020.5)

    def test_specs_validate_and_preserve_variants(self):
        self.assertEqual(
            [variant['loft_degrees'] for variant in specifications({'lofts': [9, 10.5, 12]})],
            [9, 10.5, 12],
        )
        for specs in ({'lofts': []}, {'lofts': [None]}, {'lofts': [100]},
                      {'club_length_inches': 100}, {'shaft_material': []}):
            with self.assertRaises(ValueError):
                specifications(specs)


class ImportTests(unittest.TestCase):
    def club(self, **overrides):
        club = {'brand': 'Ping', 'model': 'Driver', 'club_type': 'Driver',
                'year': datetime.now().year, 'price': 300,
                'url': 'https://example.org/driver'}
        club.update(overrides)
        return club

    def test_retail_unknown_year_is_not_fabricated(self):
        cursor = MagicMock()
        database = FakeDB(cursor)
        with patch.object(retailer, 'db', database):
            self.assertEqual(retailer.import_clubs([self.club(year=None)], 'Retailer'), (0, 0))
        cursor.execute.assert_not_called()

    def test_retail_identity_provenance_and_unknown_stock(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [{'id': 1}, {'id': 2}, None, {'id': 3}]
        database = FakeDB(cursor)
        with patch.object(retailer, 'db', database):
            self.assertEqual(retailer.import_clubs([self.club()], 'Retailer'), (1, 0))
        self.assertEqual(database.sessions, 1)
        self.assertEqual(database.commits, 1)
        queries = cursor.execute.call_args_list
        identity = next(call for call in queries if 'SELECT id FROM golf_clubs' in call.args[0])
        self.assertIn('year_released = %s', identity.args[0])
        offer = next(call for call in queries if 'INSERT INTO product_sources' in call.args[0])
        self.assertEqual(offer.args[1][1:3], ('Retailer', 'https://example.org/driver'))
        self.assertIsNone(offer.args[1][4])

    def test_retail_failure_rolls_back_whole_import(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [{'id': 1}, {'id': 2}, None, {'id': 3}]
        cursor.execute.side_effect = lambda sql, params: (
            (_ for _ in ()).throw(RuntimeError('failed offer'))
            if 'INSERT INTO product_sources' in sql else None)
        database = FakeDB(cursor)
        with patch.object(retailer, 'db', database), self.assertRaises(RuntimeError):
            retailer.import_clubs([self.club()], 'Retailer')
        self.assertEqual((database.commits, database.rollbacks), (0, 1))

    def test_retail_specs_are_validated_with_source(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [{'id': 1}, {'id': 2}, None, {'id': 3}]
        with patch.object(retailer, 'db', FakeDB(cursor)):
            self.assertEqual(retailer.import_clubs(
                [self.club(specs={'lofts': [9, 10.5]})], 'Retailer'), (1, 0))
        inserts = [call for call in cursor.execute.call_args_list
                   if 'INSERT INTO club_specifications' in call.args[0]]
        self.assertEqual([call.args[1][1] for call in inserts], [9, 10.5])
        self.assertEqual(inserts[0].args[1][-4:-1],
                         ['Retailer', 'https://example.org/driver', True])

    def test_invalid_retail_specs_make_no_database_changes(self):
        cursor = MagicMock()
        with patch.object(retailer, 'db', FakeDB(cursor)):
            self.assertEqual(retailer.import_clubs(
                [self.club(specs={'lofts': [float('nan')]})], 'Retailer'), (0, 0))
        cursor.execute.assert_not_called()

    def test_historical_all_lofts_provenance_and_validation(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [{'id': 1}, {'id': 2}, None, {'id': 3}]
        database = FakeDB(cursor)
        club = self.club(specs={'lofts': [9, 10.5], 'shaft_material': 'Graphite'})
        with patch.object(historical, 'db', database):
            self.assertEqual(historical.load_historical_clubs(
                [club], source_name='Archive', source_url='/data/source.json'), (1, 0))
        inserts = [call for call in cursor.execute.call_args_list
                   if 'INSERT INTO club_specifications' in call.args[0]]
        self.assertEqual([call.args[1][1] for call in inserts], [9, 10.5])
        self.assertEqual(inserts[0].args[1][-4:-1], ['Archive', '/data/source.json', True])
        self.assertEqual(database.sessions, 1)

    def test_historical_invalid_specs_and_unknown_year_skip(self):
        cursor = MagicMock()
        with patch.object(historical, 'db', FakeDB(cursor)):
            result = historical.load_historical_clubs(
                [self.club(specs={'lofts': [999]}), self.club(year=None)])
        self.assertEqual(result, (0, 2))
        cursor.execute.assert_not_called()

    def test_historical_reimport_enriches_existing_without_duplicate_clubs(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [{'id': 1}, {'id': 2}, {'id': 3}]
        with patch.object(historical, 'db', FakeDB(cursor)):
            self.assertEqual(historical.load_historical_clubs(
                [self.club(specs={'lofts': [9, 10.5]})], source_url='/archive.json'), (0, 1))
        sql = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertFalse(any('INSERT INTO golf_clubs' in statement for statement in sql))
        self.assertEqual(sum('INSERT INTO club_specifications' in statement for statement in sql), 2)
        self.assertTrue(any('DELETE FROM club_specifications' in statement for statement in sql))

    def test_historical_spec_failure_is_atomic(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [{'id': 1}, {'id': 2}, None, {'id': 3}]
        def execute(sql, params):
            if 'INSERT INTO club_specifications' in sql:
                raise RuntimeError('spec insert failed')
        cursor.execute.side_effect = execute
        database = FakeDB(cursor)
        with patch.object(historical, 'db', database), self.assertRaises(RuntimeError):
            historical.load_historical_clubs([self.club(specs={'lofts': [9]})])
        self.assertEqual((database.commits, database.rollbacks), (0, 1))


class ScraperTests(unittest.TestCase):
    def setUp(self):
        with patch('scrapers.base_scraper.UserAgent'):
            self.scraper = GlobalGolfScraper()
        self.addCleanup(self.scraper.close)

    def details(self, html):
        with patch.object(self.scraper, 'fetch_page', return_value=BeautifulSoup(html, 'html.parser')):
            return self.scraper.scrape_club_details('https://example.org/driver')

    def test_jsonld_price_and_stock(self):
        details = self.details('''<script type="application/ld+json">
          {"@type":"Product","offers":{"price":"299.99","priceCurrency":"USD",
          "availability":"https://schema.org/OutOfStock"}}</script>''')
        self.assertEqual(details['price'], 299.99)
        self.assertIs(details['in_stock'], False)

    def test_microdata_and_unknown_stock(self):
        details = self.details('<meta itemprop="price" content="250.50">')
        self.assertEqual(details['price'], 250.5)
        self.assertIsNone(details['in_stock'])
        self.assertIsNone(details['year'])

    def test_listing_does_not_invent_stock_or_release_year(self):
        soup = BeautifulSoup('''<div><h3 class="product-name">Ping Driver</h3>
            <a class="product-link" href="https://example.org/p"></a>
            <span class="price">$300.00</span></div>''', 'html.parser')
        data = self.scraper._extract_club_data(soup.div, 'drivers')
        self.assertIsNone(data['in_stock'])
        self.assertIsNone(data['year'])
        self.assertEqual(data['url'], 'https://example.org/p')

    def test_no_price_range_or_variant_conflation(self):
        self.assertIsNone(self.scraper.extract_price('$100 - $200'))
        details = self.details('''<script type="application/ld+json">{"@type":"Product",
           "offers":[{"price":100,"availability":"https://schema.org/OutOfStock"},
                     {"price":200,"availability":"https://schema.org/InStock"}]}</script>
                     <meta itemprop="price" content="100">
                     <meta itemprop="availability" content="https://schema.org/InStock">''')
        self.assertIsNone(details['price'])
        self.assertIsNone(details['in_stock'])

    def test_fetch_failure(self):
        with patch.object(self.scraper, 'fetch_page', return_value=None):
            self.assertIsNone(self.scraper.scrape_club_details('https://example.org/p'))


class PriceUpdateTests(unittest.TestCase):
    def test_missing_price_not_success_and_out_of_stock_clears_cache(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            {'id': 1, 'golf_club_id': 5, 'product_url': 'https://example.org/p',
             'model_name': 'Driver', 'brand_name': 'Ping'},
            {'id': 2, 'golf_club_id': 6, 'product_url': 'https://example.org/q',
             'model_name': 'Wood', 'brand_name': 'Ping'},
        ]
        scraper = MagicMock()
        scraper.scrape_club_details.side_effect = [
            {'price': None, 'in_stock': None}, {'price': None, 'in_stock': False}]
        with patch.object(update_prices, 'db', FakeDB(cursor)), patch.object(update_prices, 'log_scrape'):
            self.assertEqual(update_prices.update_prices_from_source(scraper, 'Retailer'), (1, 1))
        queries = cursor.execute.call_args_list
        self.assertTrue(any('price_checked_at' in call.args[0] for call in queries))
        refresh = next(call for call in queries if 'UPDATE golf_clubs' in call.args[0])
        self.assertIn("INTERVAL '1 day'", refresh.args[0])
        self.assertIn('in_stock IS TRUE', refresh.args[0])


class MigrationTests(unittest.TestCase):
    def test_only_new_fitting_schema_is_replayed_idempotently(self):
        schema = """CREATE TABLE brands (id INTEGER);
-- Fitting outcome tables
CREATE TABLE fitting_sessions (id INTEGER);
CREATE INDEX idx_fitting_session ON fitting_sessions(id);
CREATE UNIQUE INDEX idx_fitting_unique ON fitting_sessions(id);
"""
        with patch('pathlib.Path.read_text', return_value=schema):
            sql = migration.fitting_schema()
        self.assertNotIn('brands', sql)
        self.assertIn('CREATE TABLE IF NOT EXISTS fitting_sessions', sql)
        self.assertIn('CREATE INDEX IF NOT EXISTS idx_fitting_session', sql)
        self.assertIn('CREATE UNIQUE INDEX IF NOT EXISTS idx_fitting_unique', sql)

    def test_migration_deduplicates_newest_and_adds_unique(self):
        self.assertIn('ORDER BY last_checked DESC NULLS LAST, id DESC', migration.MIGRATION_SQL)
        self.assertIn('UNIQUE (golf_club_id, source_name)', migration.MIGRATION_SQL)
        self.assertIn('SET current_price = NULL WHERE price_updated_at IS NULL', migration.MIGRATION_SQL)
        cursor = MagicMock()
        database = FakeDB(cursor)
        with patch.object(migration, 'db', database), patch.object(
                migration, 'fitting_schema', return_value='CREATE TABLE IF NOT EXISTS fitting_sessions ();'):
            migration.migrate()
        self.assertEqual(database.sessions, 1)
        self.assertEqual(database.commits, 1)

    def test_migration_fitting_failure_rolls_back_existing_table_changes(self):
        cursor = MagicMock()
        cursor.execute.side_effect = [None, RuntimeError('fitting schema failed')]
        database = FakeDB(cursor)
        with patch.object(migration, 'db', database), patch.object(
                migration, 'fitting_schema', return_value='CREATE TABLE fitting_sessions ();'):
            with self.assertRaises(RuntimeError):
                migration.migrate()
        self.assertEqual((database.commits, database.rollbacks), (0, 1))


if __name__ == '__main__':
    unittest.main()
