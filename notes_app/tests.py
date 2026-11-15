"""Synthetic accounts only; Django creates and destroys a separate test database."""
import os
from io import StringIO
import secrets
import subprocess
import sys
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, ProgrammingError
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .forms import RegisterForm
from .models import Student


def registration(**overrides):
    password = secrets.token_urlsafe(24)
    data = dict(username='synthetic_student', first_name='Synthetic', last_name='Student',
                email='synthetic@example.invalid', reg_number='TEST-001', gender='O',
                password1=password, password2=password)
    data.update(overrides)
    return data


@override_settings(ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
                   STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                             'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class RegistrationTests(TestCase):
    def test_atomic_rollback_on_profile_failure(self):
        form = RegisterForm(registration())
        self.assertTrue(form.is_valid(), form.errors)
        with patch('notes_app.forms.Student.objects.create', side_effect=ProgrammingError('synthetic missing table')):
            with self.assertRaises(ProgrammingError):
                form.save()
        self.assertFalse(User.objects.exists())
        self.assertFalse(Student.objects.exists())

    def test_duplicate_reg_number_is_case_insensitive(self):
        user = User.objects.create_user('existing_synthetic')
        Student.objects.create(user=user, reg_number='TEST-001', gender='O')
        form = RegisterForm(registration(reg_number=' test-001 '))
        self.assertFalse(form.is_valid())
        self.assertIn('reg_number', form.errors)
        self.assertEqual(User.objects.count(), 1)

    def test_commit_false_does_not_write(self):
        form = RegisterForm(registration())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.save(commit=False).pk)
        self.assertFalse(User.objects.exists())
        self.assertFalse(Student.objects.exists())

    def test_success_normalizes_number_and_hashes_password(self):
        data = registration(reg_number=' test-123 ')
        form = RegisterForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.student.reg_number, 'TEST-123')
        self.assertTrue(user.check_password(data['password1']))
        self.assertNotEqual(user.password, data['password1'])

    def test_weak_and_mismatched_passwords_rejected(self):
        for data in [registration(password1='123', password2='123'),
                     registration(password2='does-not-match')]:
            form = RegisterForm(data)
            self.assertFalse(form.is_valid())
        self.assertFalse(User.objects.exists())

    def test_register_login_persistence_dashboard_logout(self):
        data = registration()
        self.assertRedirects(self.client.post(reverse('register'), data), reverse('home'))
        self.assertEqual(Student.objects.count(), 1)
        for route in ['home', 'units', 'notes', 'groups', 'students', 'announcements', 'reminders']:
            self.assertEqual(self.client.get(reverse(route)).status_code, 200, route)
        self.assertIn('_auth_user_id', self.client.session)
        self.assertRedirects(self.client.post(reverse('logout')), reverse('login'))
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(self.client.get(reverse('home')).status_code, 302)
        self.assertRedirects(self.client.post(reverse('login'), {
            'username': data['username'], 'password': data['password1']}), reverse('home'))
        self.assertEqual(self.client.get(reverse('home')).status_code, 200)
        self.assertIn('_auth_user_id', self.client.session)

    def test_wrong_password_cannot_login(self):
        form = RegisterForm(registration())
        self.assertTrue(form.is_valid())
        form.save()
        response = self.client.post(reverse('login'), {'username': 'synthetic_student', 'password': 'wrong'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_database_failure_returns_503_without_orphan(self):
        with patch('notes_app.forms.Student.objects.create', side_effect=ProgrammingError('synthetic missing table')):
            response = self.client.post(reverse('register'), registration())
        self.assertContains(response, 'temporarily unavailable', status_code=503)
        self.assertNotContains(response, 'synthetic missing table', status_code=503)
        self.assertFalse(User.objects.exists())
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_missing_table_during_validation_returns_503(self):
        with patch('notes_app.forms.Student.objects.filter', side_effect=ProgrammingError('synthetic missing table')):
            self.assertEqual(self.client.post(reverse('register'), registration()).status_code, 503)
        self.assertFalse(User.objects.exists())

    def test_concurrent_unique_conflict_rolls_back(self):
        with patch('notes_app.forms.Student.objects.create', side_effect=IntegrityError('synthetic duplicate')):
            response = self.client.post(reverse('register'), registration())
        self.assertContains(response, 'unavailable')
        self.assertFalse(User.objects.exists())

    def test_existing_account_is_preserved(self):
        existing = User.objects.create_user('existing_synthetic', password=secrets.token_urlsafe(24))
        student = Student.objects.create(user=existing, reg_number='EXISTING-001', gender='O')
        original_password = existing.password
        self.client.post(reverse('register'), registration())
        existing.refresh_from_db()
        self.assertEqual(existing.password, original_password)
        self.assertEqual(existing.student.pk, student.pk)
        self.assertEqual(User.objects.count(), 2)

    def test_csrf_enforced_on_authentication(self):
        client = Client(enforce_csrf_checks=True)
        for route in ['register', 'login', 'logout']:
            self.assertEqual(client.post(reverse(route), registration()).status_code, 403)
        response = client.get(reverse('register'))
        token = response.cookies['csrftoken'].value
        self.assertEqual(client.post(reverse('register'), registration(), HTTP_X_CSRFTOKEN=token).status_code, 302)
        self.assertIn('_auth_user_id', client.session)
        self.assertEqual(client.get(reverse('logout')).status_code, 405)
        self.assertIn('_auth_user_id', client.session)
        token = client.cookies['csrftoken'].value
        self.assertEqual(client.post(reverse('logout'), HTTP_X_CSRFTOKEN=token).status_code, 302)
        self.assertNotIn('_auth_user_id', client.session)

    @override_settings(SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True)
    def test_secure_cookie_flags(self):
        response = self.client.post(reverse('register'), registration(), secure=True)
        self.assertTrue(response.cookies[settings.SESSION_COOKIE_NAME]['secure'])
        self.assertTrue(response.cookies[settings.SESSION_COOKIE_NAME]['httponly'])
        self.assertEqual(response.cookies[settings.SESSION_COOKIE_NAME]['samesite'], 'Lax')
        self.assertTrue(response.cookies['csrftoken']['secure'])

    def test_unauthenticated_routes_redirect(self):
        for route in ['home', 'units', 'notes', 'groups', 'students', 'announcements', 'reminders']:
            self.assertEqual(self.client.get(reverse(route)).status_code, 302)

    @override_settings(DEBUG=False)
    def test_seed_refuses_non_development_database(self):
        with self.assertRaises(CommandError):
            call_command('seed', verbosity=0)
        self.assertFalse(User.objects.exists())

    @override_settings(DEBUG=True)
    def test_local_seed_has_no_usable_passwords_or_admin(self):
        output = StringIO()
        call_command('seed', verbosity=0, stdout=output)
        self.assertNotIn('password:', output.getvalue().lower())
        self.assertFalse(User.objects.filter(is_superuser=True).exists())
        self.assertEqual(Student.objects.count(), 2)
        self.assertTrue(all(not user.has_usable_password() for user in User.objects.all()))


class ConfigurationTests(SimpleTestCase):
    def settings_process(self, **overrides):
        env = os.environ.copy()
        for key in ['SECRET_KEY', 'DATABASE_URL', 'DEBUG', 'ALLOWED_HOSTS',
                    'CSRF_TRUSTED_ORIGINS', 'VERCEL', 'VERCEL_URL']:
            env.pop(key, None)
        env.update(SECRET_KEY=secrets.token_urlsafe(64), DEBUG='False',
                   DATABASE_URL='postgresql://placeholder:placeholder@localhost/placeholder',
                   ALLOWED_HOSTS='example.invalid')
        for key, value in overrides.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        return subprocess.run([sys.executable, '-c',
            'from IN16_Study_Manager import settings as s; '
            'assert s.DATABASES["default"].get("OPTIONS", {}).get("sslmode") == "require"; '
            'assert s.SESSION_COOKIE_SECURE and s.CSRF_COOKIE_SECURE; '
            'assert s.SECURE_SSL_REDIRECT; '
            'assert "*" not in s.ALLOWED_HOSTS'],
            env=env, capture_output=True, text=True)

    def test_production_configuration_uses_tls_and_secure_cookies(self):
        result = self.settings_process()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_or_unsafe_configuration_fails_closed(self):
        for config in [dict(SECRET_KEY=None), dict(DATABASE_URL=None),
                       dict(DATABASE_URL='sqlite:///:memory:'), dict(ALLOWED_HOSTS='*'),
                       dict(DEBUG='True', VERCEL='1')]:
            result = self.settings_process(**config)
            self.assertNotEqual(result.returncode, 0, config.keys())
            self.assertIn('ImproperlyConfigured', result.stderr)
