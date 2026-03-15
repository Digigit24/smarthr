"""Common app configuration — customises Django admin site at startup."""
from django.apps import AppConfig


class CommonConfig(AppConfig):
    name = "common"
    verbose_name = "Common"

    def ready(self):
        self._patch_admin_login_form()

    @staticmethod
    def _patch_admin_login_form():
        """Replace the default admin login form's 'Username' label with 'Email'."""
        from django import forms
        from django.contrib import admin
        from django.contrib.auth.forms import AuthenticationForm

        class EmailAuthenticationForm(AuthenticationForm):
            username = forms.CharField(
                label="Email Address",
                max_length=254,
                widget=forms.TextInput(
                    attrs={"autofocus": True, "autocomplete": "email"}
                ),
                help_text="Enter the email address you use on admin.celiyo.com",
            )

        admin.site.login_form = EmailAuthenticationForm
        admin.site.site_header = "SmartHR-In Administration"
        admin.site.site_title = "SmartHR-In Admin"
        admin.site.index_title = "SmartHR-In Dashboard"
