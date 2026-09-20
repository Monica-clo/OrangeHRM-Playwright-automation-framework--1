"""Locators for the Login page and the Dashboard landing page."""


class LoginLocators:
    USERNAME_INPUT = "input[name='username']"
    PASSWORD_INPUT = "input[name='password']"
    LOGIN_BUTTON = "button[type='submit']"
    INVALID_CREDENTIALS_ALERT = "p.oxd-alert-content-text"
    REQUIRED_FIELD_ERROR = "span.oxd-input-field-error-message"
    FORGOT_PASSWORD_LINK = "p.orangehrm-login-forgot-header"
    LOGIN_TITLE = "h5.orangehrm-login-title"


class DashboardLocators:
    DASHBOARD_WIDGETS = "div.orangehrm-dashboard-widget"
    DASHBOARD_HEADER_TEXT = "Dashboard"
