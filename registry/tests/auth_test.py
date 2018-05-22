import itsdangerous
import json
import jwt
import time
import requests
import unittest
from unittest import mock
from unittest.mock import patch
from .utils import QuiltTestCase
from quilt_server.models import Code
from quilt_server.auth import (_create_user, _delete_user, _list_users, get_user, 
        issue_token, encode_code, decode_code, generate_uuid, verify_token_string,
        generate_activation_link, generate_reset_link, verify_activation_link, verify_reset_link
        )

class AuthTestCase(QuiltTestCase):
    """
    unit tests for Flask-based auth
    """
    TEST_USER = 'test_user'
    TEST_PASSWORD = 'beans'
    OTHER_USER = 'edwin'

    def setUp(self):
        super(AuthTestCase, self).setUp()
        _create_user(self.TEST_USER, password=self.TEST_PASSWORD,
                email='{user}{suf}'.format(user=self.TEST_USER, suf=self.email_suffix),
                force=True, requires_activation=False)
        self.TEST_USER_ID = get_user(self.TEST_USER).id
        self.token_verify_mock.stop() # disable auth mock

    def getToken(self):
        response = self.app.post('/login', 
                data=json.dumps({'username': self.TEST_USER, 'password': self.TEST_PASSWORD}))
        try:
            token = json.loads(response.data.decode('utf8')).get('token')
        except Exception as e:
            raise Exception(response.data.decode('utf8'))
        return token

    def decodeToken(self, token):
        return jwt.decode(token, verify=False)

    def testCodeRoundtrips(self):
        code = {'id': generate_uuid(), 'code': generate_uuid()}
        assert code == decode_code(encode_code(code))

    def testIssueToken(self):
        issue_token(self.TEST_USER)

    def testDeleteUser(self):
        _create_user(self.OTHER_USER, force=True, requires_activation=False)
        assert get_user(self.OTHER_USER)
        _delete_user(self.OTHER_USER)
        assert not get_user(self.OTHER_USER)

    def testCreateNewUser(self):
        _create_user(self.OTHER_USER, force=True, requires_activation=False)
        assert get_user(self.OTHER_USER)

    def testUserExists(self):
        assert get_user(self.TEST_USER)

    def testDuplicateUserFails(self):
        try:
            _create_user(self.TEST_USER, requires_activation=False)
        except:
            return True
        raise Exception('Creating duplicate user failed to raise')

    def testListUsers(self):
        _list_users()

    def testLoginUserPass(self):
        token = self.getToken()
        assert token

    def testVerifyTokenAsString(self):
        token = self.getToken()
        assert verify_token_string(token)

    def testRefreshToken(self):
        # try to exchange a token for a new one that expires later
        token = self.getToken()
        t = self.decodeToken(token)
        exp = t.get('exp')

        auth_headers = {
            'Authorization': token,
            'content-type': 'application/json'
        }
        api_root_request = self.app.get(
            '/api-root',
            headers=auth_headers
        )
        assert api_root_request.status_code == 200

        time.sleep(2)
        auth_headers = {
            'Authorization': token,
            'content-type': 'application/json'
        }
        new_token_request = self.app.post(
                '/api/refresh',
                headers=auth_headers
            )

        new_token = json.loads(new_token_request.data.decode('utf8')).get('token')
        new_exp = self.decodeToken(new_token).get('exp')
        assert new_exp > exp

    def testActivationLink(self):
        link = generate_activation_link(self.TEST_USER_ID)
        assert verify_activation_link(link)

    def testResetLink(self):
        link = generate_reset_link(self.TEST_USER_ID)
        payload = verify_reset_link(link)
        assert payload
        assert payload['id']

    def testLinksExpire(self):
        activate_link = generate_activation_link(self.TEST_USER_ID)
        reset_link = generate_reset_link(self.TEST_USER_ID)
        time.sleep(1)
        assert not verify_activation_link(activate_link, 0)
        assert not verify_reset_link(reset_link, 0)

    def testWrongLinksShouldFail(self):
        activate_link = generate_activation_link(self.TEST_USER_ID)
        reset_link = generate_reset_link(self.TEST_USER_ID)
        assert not verify_reset_link(activate_link)
        assert not verify_activation_link(reset_link)

    @patch('quilt_server.auth.send_activation_email')
    def testRegister(self, send_activation_email):
        user = 'new_user'
        email = 'new_user@example.com'
        password = 'example_password'
        response = self.app.post(
            '/register',
            headers={'content-type': 'application/json'},
            data=json.dumps(
                {'username': user,
                 'email': email,
                 'password': password}
            )
        )
        assert response.status_code == 200
        assert send_activation_email.called
        user = send_activation_email.call_args[0][0]
        link = send_activation_email.call_args[0][1]

        activate_response = self.app.get(
            '/activate/{link}'.format(link=link)
        )
        assert activate_response.status_code == 302

    @patch('quilt_server.auth.send_reset_email')
    def testReset(self, send_reset_email):
        user = self.TEST_USER
        email = '{user}{suf}'.format(user=user, suf=self.email_suffix)
        new_password = 'new_password'
        response = self.app.post(
            '/reset_password',
            headers={'content-type': 'application/json'},
            data=json.dumps({'email': 'user-that-definitely-does-not-exist{suf}'
                .format(suf=self.email_suffix)})
        )
        assert response.status_code == 200
        assert not send_reset_email.called
        assert self.getToken()

        response = self.app.post(
            '/reset_password',
            headers={'content-type': 'application/json'},
            data=json.dumps({'email': email})
        )

        assert response.status_code == 200
        assert send_reset_email.called
        assert self.getToken() # old password still works

        called_user = send_reset_email.call_args[0][0]
        assert called_user.name == user
        assert called_user.email == email
        reset_link = send_reset_email.call_args[0][1]

        reset_response = self.app.post(
            '/reset_password',
            headers={'content-type': 'application/json'},
            data=json.dumps({'link': reset_link, 'password': new_password})
        )
        assert reset_response.status_code == 200
        assert not self.getToken()

        new_password_request = self.app.post('/login', 
                data=json.dumps({'username': self.TEST_USER, 'password': new_password}))
        assert new_password_request.status_code == 200
        assert json.loads(new_password_request.data.decode('utf8')).get('token')

    def testGetCode(self):
        token = self.getToken()
        code_request = self.app.get(
            '/api/code',
            headers={
                'Authorization': token,
                'content-type': 'application/json'
            }
        )
        assert code_request.status_code == 200


    def testCompilerLogin(self):
        # get initial token
        token = self.getToken()
        # request code
        code_request = self.app.get(
            '/api/code',
            headers={
                'Authorization': token,
                'content-type': 'application/json'
            }
        )
        assert code_request.status_code == 200
        code = json.loads(code_request.data.decode('utf8')).get('code')

        # exchange code for token
        token_request = self.app.post(
            '/api/token',
            data={'refresh_token': code}
        )
        assert token_request.status_code == 200
        payload = json.loads(token_request.data.decode('utf8'))
        assert payload['access_token'] == payload['refresh_token']
        assert 'expires_at' in payload
        old_exp = payload['expires_at']
        new_token = payload['refresh_token']

        # refresh token
        refresh_request = self.app.post(
            '/api/token',
            data={'refresh_token': new_token}
        )
        assert refresh_request.status_code == 200
        refreshed_token_payload = json.loads(refresh_request.data.decode('utf8'))
        assert 'expires_at' in refreshed_token_payload
        assert refreshed_token_payload['access_token'] == refreshed_token_payload['refresh_token']
        pass



    # password reset emails
    # account creation flow
    # one-time codes
    # compiler login flow
    # compiler refresh
    # anti-forgery, expiration, etc
    # test logout revokes code + tokens
    # test disabling a user revokes code + tokens
    # test deleting a user revokes code + tokens
    # migrate models to id-based instead of name-based primary keys
