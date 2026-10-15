from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase

User = get_user_model()


class UserModelTests(TestCase):
    def test_email_is_normalized_and_username_kept_as_typed(self):
        user = User.objects.create_user("  Ali@Example.COM ", "AliVeli_1", "uzun-bir-parola-123")
        self.assertEqual(user.email, "ali@example.com")
        self.assertEqual(user.username, "AliVeli_1")

    def test_password_is_hashed_with_argon2(self):
        user = User.objects.create_user("a@example.com", "ali", "uzun-bir-parola-123")
        self.assertTrue(user.password.startswith("argon2"))
        self.assertTrue(user.check_password("uzun-bir-parola-123"))

    def test_duplicate_email_rejected_case_insensitively(self):
        User.objects.create_user("a@example.com", "ali", "uzun-bir-parola-123")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user("A@EXAMPLE.com", "veli", "uzun-bir-parola-123")

    def test_duplicate_username_rejected_case_insensitively(self):
        User.objects.create_user("a@example.com", "Ali", "uzun-bir-parola-123")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user("b@example.com", "aLI", "uzun-bir-parola-123")

    def test_duplicate_username_fails_validation_with_turkish_message(self):
        User.objects.create_user("a@example.com", "Ali", "uzun-bir-parola-123")
        other = User(email="b@example.com", username="ALI")
        with self.assertRaises(ValidationError) as ctx:
            other.full_clean(exclude=["password"])
        self.assertIn("Bu kullanıcı adı zaten alınmış.", str(ctx.exception))

    def test_invalid_usernames_rejected(self):
        for bad in ("ab", "a" * 21, "ali veli", "ali-veli", "çağlar", "ali@x"):
            user = User(email="x@example.com", username=bad)
            with self.assertRaises(ValidationError, msg=bad):
                user.full_clean(exclude=["password"])

    def test_valid_usernames_accepted(self):
        for good in ("abc", "Ali_Veli_99", "a" * 20):
            user = User(email=f"{good}@example.com", username=good)
            user.full_clean(exclude=["password"])

    def test_str_never_exposes_email(self):
        user = User.objects.create_user("gizli@example.com", "ali", "uzun-bir-parola-123")
        self.assertEqual(str(user), "ali")
        self.assertNotIn("gizli@example.com", user.get_full_name())

    def test_no_first_or_last_name_fields(self):
        field_names = {f.name for f in User._meta.get_fields()}
        self.assertNotIn("first_name", field_names)
        self.assertNotIn("last_name", field_names)

    def test_create_superuser(self):
        admin = User.objects.create_superuser("root@example.com", "root", "uzun-bir-parola-123")
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_createsuperuser_command_non_interactive(self):
        call_command(
            "createsuperuser",
            interactive=False,
            email="cmd@example.com",
            username="cmduser",
            verbosity=0,
        )
        self.assertTrue(User.objects.get(email="cmd@example.com").is_superuser)

    def test_login_with_email_case_insensitive(self):
        User.objects.create_user("a@example.com", "ali", "uzun-bir-parola-123")
        self.assertTrue(self.client.login(username="A@Example.com", password="uzun-bir-parola-123"))
        self.assertFalse(self.client.login(username="a@example.com", password="yanlis-parola-123"))


class PasswordPolicyTests(TestCase):
    def test_short_password_rejected(self):
        with self.assertRaises(ValidationError):
            validate_password("Kisa1234")  # 8 karakter

    def test_common_password_rejected(self):
        with self.assertRaises(ValidationError):
            validate_password("password123")

    def test_numeric_password_rejected(self):
        with self.assertRaises(ValidationError):
            validate_password("1357924680135")

    def test_strong_password_accepted(self):
        validate_password("mavi-bulut-kahve-42")

    def test_password_validation_messages_are_turkish(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_password("kisa")
        self.assertIn("En az 10 karakter", " ".join(ctx.exception.messages))
