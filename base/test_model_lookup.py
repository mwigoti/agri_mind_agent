import os
from unittest.mock import patch

from django.test import SimpleTestCase

from base import views


class ModelLookupFallbackTests(SimpleTestCase):
    def test_get_model_falls_back_to_base_when_env_label_is_wrong(self):
        with patch.dict(os.environ, {"DJANGO_APP_LABEL": "fields"}, clear=False):
            model = views._get_model("Field")
            self.assertEqual(model._meta.label_lower, "base.field")
