# -*- coding: utf-8 -*-
from __future__ import absolute_import

import datetime
import re
import string
import sys
import unittest

import django
from django.db import connection
from django.db import models

from .fields import (
    EncryptedCharField, EncryptedDateField,
    EncryptedDateTimeField, EncryptedIntField,
    EncryptedLongField, EncryptedFloatField, PickleField,
    EncryptedUSPhoneNumberField, EncryptedUSSocialSecurityNumberField,
    EncryptedEmailField,
)

if django.VERSION[1] > 9:
    DJANGO_1_10 = True
else:
    DJANGO_1_10 = False

if sys.version_info[0] == 3:
    PYTHON3 = True
else:
    PYTHON3 = False


class EncObject(models.Model):
    max_password = 100
    password = EncryptedCharField(max_length=max_password, null=True)

    class Meta:
        app_label = 'django_fields'


class EncDate(models.Model):
    important_date = EncryptedDateField()

    class Meta:
        app_label = 'django_fields'


class EncDateTime(models.Model):
    important_datetime = EncryptedDateTimeField()
    # important_datetime = EncryptedDateField()

    class Meta:
        app_label = 'django_fields'


class EncInt(models.Model):
    important_number = EncryptedIntField()

    class Meta:
        app_label = 'django_fields'


class EncLong(models.Model):
    important_number = EncryptedLongField()

    class Meta:
        app_label = 'django_fields'


class EncFloat(models.Model):
    important_number = EncryptedFloatField()

    class Meta:
        app_label = 'django_fields'


class PickleObject(models.Model):
    name = models.CharField(max_length=16)
    data = PickleField()

    class Meta:
        app_label = 'django_fields'


class EmailObject(models.Model):
    max_email = 255
    email = EncryptedEmailField(max_length=max_email)

    class Meta:
        app_label = 'django_fields'


class USPhoneNumberField(models.Model):
    phone = EncryptedUSPhoneNumberField()

    class Meta:
        app_label = 'django_fields'


class USSocialSecurityNumberField(models.Model):
    ssn = EncryptedUSSocialSecurityNumberField()

    class Meta:
        app_label = 'django_fields'


class CipherEncObject(models.Model):
    max_password = 20
    password = EncryptedCharField(
        max_length=max_password,
        block_type='MODE_CBC')

    class Meta:
        app_label = 'django_fields'


class CipherEncDate(models.Model):
    important_date = EncryptedDateField(block_type='MODE_CBC')

    class Meta:
        app_label = 'django_fields'


class EncryptTests(unittest.TestCase):

    def setUp(self):
        EncObject.objects.all().delete()

    def test_encryption(self):
        """
        Test that the database values are actually encrypted.
        """
        password = 'this is a password!!'  # 20 chars
        obj = EncObject(password = password)
        obj.save()
        # The value from the retrieved object should be the same...
        obj = EncObject.objects.get(id=obj.id)
        self.assertEqual(password, obj.password)
        # ...but the value in the database should not
        encrypted_password = self._get_encrypted_password(obj.id)
        self.assertNotEqual(encrypted_password, password)
        self.assertTrue(encrypted_password.startswith('$AES$'))

    def test_encryption_w_cipher(self):
        """
        Test that the database values are actually encrypted when using
        non-default cipher types.
        """
        password = 'this is a password!!'  # 20 chars
        obj = CipherEncObject(password = password)
        obj.save()
        # The value from the retrieved object should be the same...
        obj = CipherEncObject.objects.get(id=obj.id)
        self.assertEqual(password, obj.password)
        # ...but the value in the database should not
        encrypted_password = self._get_encrypted_password_cipher(obj.id)
        self.assertNotEqual(encrypted_password, password)
        self.assertTrue(encrypted_password.startswith('$AES$MODE_CBC$'))

    def test_multiple_encryption_w_cipher(self):
        """
        Test that a single field can be reused without error.
        """
        password = 'this is a password!!'
        obj = CipherEncObject(password=password)
        obj.save()
        obj = CipherEncObject.objects.get(id=obj.id)
        self.assertEqual(password, obj.password)

        password = 'another password!!'
        obj = CipherEncObject(password=password)
        obj.save()
        obj = CipherEncObject.objects.get(id=obj.id)
        self.assertEqual(password, obj.password)

    def test_max_field_length(self):
        password = 'a' * EncObject.max_password
        obj = EncObject(password = password)
        obj.save()
        obj = EncObject.objects.get(id=obj.id)
        self.assertEqual(password, obj.password)

    def test_field_too_long(self):
        password = 'a' * (EncObject.max_password + 1)
        obj = EncObject(password = password)
        self.assertRaises(Exception, obj.save)

    def test_UTF8(self):
        password = u'???????????????????? ????????????????'
        obj = EncObject(password = password)
        obj.save()
        obj = EncObject.objects.get(id=obj.id)
        self.assertEqual(password, obj.password)

    def test_consistent_encryption(self):
        """
        The same password should not encrypt the same way twice.
        Check different lengths.
        """
        # NOTE:  This may fail occasionally because the randomly-generated padding could be the same for both values.
        # A 14-char string will only have 1 char of padding.  There's a 1/len(string.printable) chance of getting the
        # same value twice.
        for pwd_length in range(1,21):  # 1-20 inclusive
            enc_pwd_1, enc_pwd_2 = self._get_two_passwords(pwd_length)
            self.assertNotEqual(enc_pwd_1, enc_pwd_2)

    def test_minimum_padding(self):
        """
        There should always be at least two chars of padding.
        """
        enc_field = EncryptedCharField()
        for pwd_length in range(1,21):  # 1-20 inclusive
            password = 'a' * pwd_length  # 'a', 'aa', ...
            self.assertTrue(enc_field._get_padding(password) >= 2)

    def test_none_value(self):
        """
        A value of None should be passed through without encryption.
        """
        obj = EncObject(password=None)
        obj.save()
        obj = EncObject.objects.get(id=obj.id)
        self.assertEqual(obj.password, None)
        encrypted_text = self._get_encrypted_password(obj.id)
        self.assertEqual(encrypted_text, None)

    ### Utility methods for tests ###

    def _get_encrypted_password(self, id):
        cursor = connection.cursor()
        cursor.execute("select password from django_fields_encobject where id = %s", [id,])
        passwords = list(map(lambda x: x[0], cursor.fetchall()))
        self.assertEqual(len(passwords), 1)  # only one
        return passwords[0]

    def _get_encrypted_password_cipher(self, id):
        cursor = connection.cursor()
        cursor.execute("select password from django_fields_cipherencobject where id = %s", [id,])
        passwords = list(map(lambda x: x[0], cursor.fetchall()))
        self.assertEqual(len(passwords), 1)  # only one
        return passwords[0]

    def _get_two_passwords(self, pwd_length):
        password = 'a' * pwd_length  # 'a', 'aa', ...
        obj_1 = EncObject(password = password)
        obj_1.save()
        obj_2 = EncObject(password = password)
        obj_2.save()
        # The encrypted values in the database should be different.
        # There's a chance they'll be the same, but it's small.
        enc_pwd_1 = self._get_encrypted_password(obj_1.id)
        enc_pwd_2 = self._get_encrypted_password(obj_2.id)
        return enc_pwd_1, enc_pwd_2


class DateEncryptTests(unittest.TestCase):
    def setUp(self):
        EncDate.objects.all().delete()

    def test_BC_date(self):
        # datetime.MINYEAR is 1 -- so much for history
        func = lambda: datetime.date(0, 1, 1)
        self.assertRaises(ValueError, func)

    def test_date_encryption(self):
        today = datetime.date.today()
        obj = EncDate(important_date=today)
        obj.save()
        # The date from the retrieved object should be the same...
        obj = EncDate.objects.get(id=obj.id)
        self.assertEqual(today, obj.important_date)
        # ...but the value in the database should not
        important_date = self._get_encrypted_date(obj.id)
        self.assertTrue(important_date.startswith('$AES$'))
        self.assertNotEqual(important_date, today)

    def test_date_time_encryption(self):
        now = datetime.datetime.now()
        obj = EncDateTime(important_datetime=now)
        obj.save()
        # The datetime from the retrieved object should be the same...
        obj = EncDateTime.objects.get(id=obj.id)
        self.assertEqual(now, obj.important_datetime)
        # ...but the value in the database should not
        important_datetime = self._get_encrypted_datetime(obj.id)
        self.assertTrue(important_datetime.startswith('$AES$'))
        self.assertNotEqual(important_datetime, now)

    def test_date_encryption_w_cipher(self):
        today = datetime.date.today()
        obj = CipherEncDate(important_date=today)
        obj.save()
        # The date from the retrieved object should be the same...
        obj = CipherEncDate.objects.get(id=obj.id)
        self.assertEqual(today, obj.important_date)
        # ...but the value in the database should not
        important_date = self._get_encrypted_date_cipher(obj.id)
        self.assertTrue(important_date.startswith('$AES$MODE_CBC$'))
        self.assertNotEqual(important_date, today)

    ### Utility methods for tests ###

    def _get_encrypted_date(self, id):
        cursor = connection.cursor()
        cursor.execute("select important_date from django_fields_encdate where id = %s", [id,])
        important_dates = list(map(lambda x: x[0], cursor.fetchall()))
        self.assertEqual(len(important_dates), 1)  # only one
        return important_dates[0]

    def _get_encrypted_datetime(self, id):
        cursor = connection.cursor()
        cursor.execute("select important_datetime from django_fields_encdatetime where id = %s", [id,])
        important_datetimes = list(map(lambda x: x[0], cursor.fetchall()))
        self.assertEqual(len(important_datetimes), 1)  # only one
        return important_datetimes[0]

    def _get_encrypted_date_cipher(self, id):
        cursor = connection.cursor()
        cursor.execute("select important_date from django_fields_cipherencdate where id = %s", [id,])
        important_dates = list(map(lambda x: x[0], cursor.fetchall()))
        self.assertEqual(len(important_dates), 1)  # only one
        return important_dates[0]


class NumberEncryptTests(unittest.TestCase):
    def setUp(self):
        EncInt.objects.all().delete()
        EncLong.objects.all().delete()
        EncFloat.objects.all().delete()

    def test_int_encryption(self):
        if PYTHON3 is True:
            self._test_number_encryption(EncInt, 'int', sys.maxsize)
        else:
            self._test_number_encryption(EncInt, 'int', sys.maxint)

    def test_min_int_encryption(self):
        if PYTHON3 is True:
            self._test_number_encryption(EncInt, 'int', -sys.maxsize - 1)
        else:
            self._test_number_encryption(EncInt, 'int', -sys.maxint - 1)

    def test_long_encryption(self):
        if PYTHON3 is True:
            self._test_number_encryption(
                EncLong, 'long', int(sys.maxsize) * 100)
        else:
            self._test_number_encryption(
                EncLong, 'long', long(sys.maxint) * long(100))

    def test_float_encryption(self):
        if PYTHON3 is True:
            value = 123.456 + sys.maxsize
        else:
            value = 123.456 + sys.maxint
        self._test_number_encryption(EncFloat, 'float', value)

    def test_one_third_float_encryption(self):
        if PYTHON3 is True:
            value = sys.maxsize + (1.0 / 3.0)
        else:
            value = sys.maxint + (1.0 / 3.0)
        self._test_number_encryption(EncFloat, 'float', value)

    def _test_number_encryption(self, number_class, type_name, value):
        obj = number_class(important_number=value)
        obj.save()
        # The int from the retrieved object should be the same...
        obj = number_class.objects.get(id=obj.id)
        self.assertEqual(value, obj.important_number)
        # ...but the value in the database should not
        number = self._get_encrypted_number(type_name, obj.id)
        self.assertTrue(number.startswith('$AES$'))
        self.assertNotEqual(number, value)

    def _get_encrypted_number(self, type_name, id):
        cursor = connection.cursor()
        sql = "select important_number from django_fields_enc%s where id = %%s" % (type_name,)
        cursor.execute(sql, [id,])
        important_numbers = list(map(lambda x: x[0], cursor.fetchall()))
        self.assertEqual(len(important_numbers), 1)  # only one
        return important_numbers[0]


class TestPickleField(unittest.TestCase):
    def setUp(self):
        PickleObject.objects.all().delete()

    def test_not_string_data(self):
        items = [
            'Item 1', 'Item 2', 'Item 3', 'Item 4', 'Item 5'
        ]

        obj = PickleObject.objects.create(name='default', data=items)
        self.assertEqual(PickleObject.objects.count(), 1)

        self.assertEqual(obj.data, items)

        obj = PickleObject.objects.get(name='default')
        self.assertEqual(obj.data, items)

    def test_string_and_unicode_data(self):
        DATA = (
            ('string', 'Simple string'),
            ('unicode', u'Simple unicode string'),
        )

        for name, data in DATA:
            obj = PickleObject.objects.create(name=name, data=data)
            self.assertEqual(obj.data, data)

        self.assertEqual(PickleObject.objects.count(), 2)

        for name, data in DATA:
            obj = PickleObject.objects.get(name=name)
            self.assertEqual(obj.data, data)

    def test_empty_string(self):
        value = ''

        obj = PickleObject.objects.create(name='default', data=value)
        self.assertEqual(PickleObject.objects.count(), 1)

        self.assertEqual(obj.data, value)


class EncryptEmailTests(unittest.TestCase):

    def setUp(self):
        EmailObject.objects.all().delete()

    def test_encryption(self):
        """
        Test that the database values are actually encrypted.
        """
        email = 'test@example.com'  # 16 chars
        obj = EmailObject(email = email)
        obj.save()
        # The value from the retrieved object should be the same...
        obj = EmailObject.objects.get(id=obj.id)
        self.assertEqual(email, obj.email)
        # ...but the value in the database should not
        encrypted_email = self._get_encrypted_email(obj.id)
        self.assertNotEqual(encrypted_email, email)
        self.assertTrue(encrypted_email.startswith('$AES$'))

    def test_max_field_length(self):
        email = 'a' * EmailObject.max_email
        obj = EmailObject(email = email)
        obj.save()
        obj = EmailObject.objects.get(id=obj.id)
        self.assertEqual(email, obj.email)

    def test_UTF8(self):
        email = u'????????????????????@????????????????.com'
        obj = EmailObject(email = email)
        obj.save()
        obj = EmailObject.objects.get(id=obj.id)
        self.assertEqual(email, obj.email)

    def test_consistent_encryption(self):
        """
        The same password should not encrypt the same way twice.
        Check different lengths.
        """
        # NOTE:  This may fail occasionally because the randomly-generated padding could be the same for both values.
        # A 14-char string will only have 1 char of padding.  There's a 1/len(string.printable) chance of getting the
        # same value twice.
        for email_length in range(1,21):  # 1-20 inclusive
            enc_email_1, enc_email_2 = self._get_two_emails(email_length)
            self.assertNotEqual(enc_email_1, enc_email_2)

    def test_minimum_padding(self):
        """
        There should always be at least two chars of padding.
        """
        enc_field = EncryptedCharField()
        for pwd_length in range(1,21):  # 1-20 inclusive
            email = 'a' * pwd_length  # 'a', 'aa', ...
            self.assertTrue(enc_field._get_padding(email) >= 2)

    ### Utility methods for tests ###

    def _get_encrypted_email(self, id):
        cursor = connection.cursor()
        cursor.execute("select email from django_fields_emailobject where id = %s", [id,])
        emails = list(map(lambda x: x[0], cursor.fetchall()))
        self.assertEqual(len(emails), 1)  # only one
        return emails[0]

    def _get_two_emails(self, email_length):
        email = 'a' * email_length  # 'a', 'aa', ...
        obj_1 = EmailObject(email = email)
        obj_1.save()
        obj_2 = EmailObject(email = email)
        obj_2.save()
        # The encrypted values in the database should be different.
        # There's a chance they'll be the same, but it's small.
        enc_email_1 = self._get_encrypted_email(obj_1.id)
        enc_email_2 = self._get_encrypted_email(obj_2.id)
        return enc_email_1, enc_email_2



class DatabaseSchemaTests(unittest.TestCase):
    def test_cipher_storage_length_versus_schema_length(self):
        password = 'this is a password!!'  # 20 chars
        obj = CipherEncObject(password=password)
        obj.save()
        # Get the raw (encrypted) value from the database
        raw_value = self._get_raw_password_value(obj.id)
        column_width = self._get_password_field_column_width()
        # The raw value should fit within the column width
        self.assertLessEqual(len(raw_value), column_width)

    ### Utility methods for tests ###

    def _get_raw_password_value(self, id):
        cursor = connection.cursor()
        cursor.execute("select password from django_fields_cipherencobject where id = %s", [id, ])
        passwords = list(map(lambda x: x[0], cursor.fetchall()))
        self.assertEqual(len(passwords), 1)  # only one
        return passwords[0]

    def _get_password_field_column_width(self):
        # This only works in SQLite; if you change the
        # type of database used for testing, the type
        # returned from get_table_description might be
        # different!
        cursor = connection.cursor()
        table_description = connection.introspection.get_table_description(cursor, 'django_fields_cipherencobject')
        # The first field in the tuple is the column name
        password_field = [field for field in table_description if field[0] == 'password']
        self.assertEqual(len(password_field), 1)
        password_field = password_field[0]
        # if django < 1.10
        # The second field contains the type;
        # this is something like u'varchar(78)'
        if DJANGO_1_10 is False:
            raw_type = password_field[1]
            matches = re.match('varchar\((\d+)\)', raw_type.lower())
            self.assertNotEqual(matches, None)
            column_width = int(matches.groups()[0])
            return column_width
        else:
            raw_type = password_field.internal_size
            return raw_type
