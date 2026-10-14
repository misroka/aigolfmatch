"""HTTP flow and security regression tests without external services."""

import unittest
from unittest.mock import patch
from werkzeug.security import generate_password_hash
from web import app as web


class WebTests(unittest.TestCase):
    def setUp(self):
        web.app.config.update(TESTING=True, SECRET_KEY='test-session-key')
        web._request_windows.clear()
        self.client = web.app.test_client()
        with self.client.session_transaction() as session:
            session['csrf_token'] = 'test-csrf'
        self.headers = {'X-CSRF-Token': 'test-csrf'}

    def test_questionnaire_is_public_and_issues_session(self):
        response = self.client.get('/recommend')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Find clubs that fit your game', response.data)
        with self.client.session_transaction() as session:
            self.assertTrue(session['golfer_id'])
        self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')

    def test_csrf_required_and_no_database_access(self):
        with patch.object(web, 'get_recommendation_candidates') as candidates:
            for endpoint, method in [('/api/recommendations', 'post'),
                                     ('/api/outcomes', 'post'),
                                     ('/api/outcomes', 'delete'),
                                     ('/login', 'post')]:
                response = getattr(self.client, method)(endpoint, json={})
                self.assertEqual(response.status_code, 400)
            candidates.assert_not_called()

    def test_non_object_json_rejected(self):
        for data in [None, [], 'text', 7]:
            response = self.client.post('/api/recommendations', json=data, headers=self.headers)
            self.assertEqual(response.status_code, 400)

    def test_recommendations_use_validated_profile_without_saving(self):
        profile = {'club_type': 'Driver'}
        with patch.object(web, 'validate_profile', return_value=profile), \
                patch.object(web, 'get_recommendation_candidates', return_value=[]) as candidates, \
                patch.object(web, 'recommend', return_value=[]) as recommend, \
                patch.object(web, 'save_fitting_outcome') as save, \
                patch.dict(web.os.environ, {'RECOMMENDER_MODEL_PATH': ''}):
            response = self.client.post('/api/recommendations', json={}, headers=self.headers)
            self.assertEqual(response.status_code, 200)
            candidates.assert_called_once_with('Driver')
            recommend.assert_called_once_with(profile, [], model=None, limit=5)
            save.assert_not_called()

    def test_invalid_model_and_withdrawn_consent_fall_back(self):
        for invalid in [False, True]:
            with patch.object(web, 'validate_profile', return_value={'club_type': 'Driver'}), \
                    patch.object(web, 'get_recommendation_candidates', return_value=[]), \
                    patch.object(web, 'load_model', side_effect=ValueError('bad model') if invalid else None,
                                 return_value={'quality_gate': 'passed', 'outcome_ids': [1]}), \
                    patch.object(web, 'is_model_current', return_value=False), \
                    patch.object(web, 'recommend', return_value=[]) as recommend, \
                    patch.dict(web.os.environ, {'RECOMMENDER_MODEL_PATH': '/tmp/model.json'}):
                response = self.client.post('/api/recommendations', json={}, headers=self.headers)
                self.assertEqual(response.status_code, 200)
                self.assertIsNone(recommend.call_args.kwargs['model'])

    def test_validation_and_database_errors_are_distinct(self):
        with patch.object(web, 'validate_profile', side_effect=ValueError('Invalid budget')):
            response = self.client.post('/api/recommendations', json={}, headers=self.headers)
            self.assertEqual(response.status_code, 400)
        with patch.object(web, 'validate_profile', return_value={'club_type': 'Driver'}), \
                patch.object(web, 'get_recommendation_candidates', side_effect=RuntimeError('private details')):
            response = self.client.post('/api/recommendations', json={}, headers=self.headers)
            self.assertEqual(response.status_code, 503)
            self.assertNotIn(b'private details', response.data)

    def test_feedback_identity_assigned_server_side(self):
        with patch.object(web, 'validate_outcome', side_effect=lambda payload: payload), \
                patch.object(web, 'save_fitting_outcome', return_value=42) as save:
            response = self.client.post('/api/outcomes', json={'golfer_id': 'impersonate'},
                                        headers=self.headers)
            self.assertEqual(response.status_code, 201)
            identity = save.call_args.args[0]['golfer_id']
            self.assertNotEqual(identity, 'impersonate')
            with self.client.session_transaction() as session:
                self.assertEqual(identity, session['golfer_id'])

    def test_withdrawal_scoped_to_browser_session(self):
        with self.client.session_transaction() as session:
            session['golfer_id'] = 'session-owner'
        with patch.object(web, 'delete_fitting_outcomes', return_value=2) as delete:
            response = self.client.delete('/api/outcomes', json={'golfer_id': 'someone-else'},
                                          headers=self.headers)
            self.assertEqual(response.json, {'deleted': 2})
            delete.assert_called_once_with('session-owner')

    def test_admin_views_remain_private(self):
        for path in ['/', '/profiles', '/api/recommendation-health']:
            self.assertEqual(self.client.get(path).status_code, 302)

    def test_login_blocks_external_redirects_and_missing_password(self):
        with patch.object(web, 'ADMIN_PASSWORD_HASH', generate_password_hash('test-only-password')):
            self.assertEqual(self.client.post('/login', data={'username': web.ADMIN_USERNAME},
                                              headers=self.headers).status_code, 200)
            for target in ['https://example.com', '//example.com', '/\\example.com']:
                response = self.client.post('/login', query_string={'next': target},
                                            data={'username': web.ADMIN_USERNAME, 'password': 'test-only-password'},
                                            headers=self.headers)
                self.assertEqual(response.headers['Location'], '/')
                self.client.post('/logout', headers=self.headers)
            response = self.client.post('/login', query_string={'next': '/clubs'},
                                        data={'username': web.ADMIN_USERNAME, 'password': 'test-only-password'},
                                        headers=self.headers)
            self.assertEqual(response.headers['Location'], '/clubs')

    def test_get_logout_cannot_change_session(self):
        self.assertEqual(self.client.get('/logout').status_code, 405)

    def test_rate_limit_and_request_size(self):
        with patch.object(web, 'validate_profile', side_effect=ValueError('invalid')):
            for _ in range(20):
                self.client.post('/api/recommendations', json={}, headers=self.headers)
            response = self.client.post('/api/recommendations', json={}, headers=self.headers)
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.headers['Retry-After'], '60')
        response = self.client.post('/api/outcomes', json={'padding': 'x' * 17000}, headers=self.headers)
        self.assertEqual(response.status_code, 413)


if __name__ == '__main__':
    unittest.main()
