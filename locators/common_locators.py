"""Locators shared by every OrangeHRM page (header, side menu, toasts, form widgets).

OrangeHRM renders every form field as:
    <div class="oxd-input-group">
        <div class="oxd-input-group__label-wrapper"><label>Employee Id</label></div>
        <div><input class="oxd-input"></div>
    </div>
so the *_BY_LABEL templates find a field by its visible label text - the same text
you see in the screenshots. Use them with .format(label="Employee Id").
"""

_INPUT_GROUP = "/ancestor::div[contains(concat(' ', normalize-space(@class), ' '), ' oxd-input-group ')][1]"


class CommonLocators:
    # ---------- label based templates (XPath) ----------
    INPUT_BY_LABEL = '//label[normalize-space(.)="{label}"]' + _INPUT_GROUP + "//input"
    TEXTAREA_BY_LABEL = '//label[normalize-space(.)="{label}"]' + _INPUT_GROUP + "//textarea"
    SELECT_BY_LABEL = (
        '//label[normalize-space(.)="{label}"]' + _INPUT_GROUP
        + "//div[contains(concat(' ', normalize-space(@class), ' '), ' oxd-select-text ')]"
    )
    FIELD_ERROR_BY_LABEL = (
        '//label[normalize-space(.)="{label}"]' + _INPUT_GROUP
        + "//span[contains(@class, 'oxd-input-field-error-message')]"
    )
    RADIO_LABEL = '//label[normalize-space(.)="{label}"]'
    RADIO_INPUT = '//label[normalize-space(.)="{label}"]//input[@type="radio"]'

    # ---------- custom dropdown (oxd-select) ----------
    DROPDOWN_LISTBOX = "div[role='listbox']"
    DROPDOWN_OPTION = "div[role='option']"
    DROPDOWN_SELECTED_TEXT = "div.oxd-select-text-input"

    # ---------- feedback ----------
    TOAST = "div.oxd-toast"
    TOAST_MESSAGE = "p.oxd-text--toast-message"
    FORM_LOADER = "div.oxd-form-loader"
    FIELD_ERROR = "span.oxd-input-field-error-message"
    SUBMIT_BUTTON = "button[type='submit']"

    # ---------- top bar (orange header in all screenshots) ----------
    MODULE_HEADER = "h6.oxd-topbar-header-breadcrumb-module"      # "PIM" / "Dashboard"
    USER_DROPDOWN = "span.oxd-userdropdown-tab"                    # "Bilol AbdurasulUser ▼"
    USER_DROPDOWN_NAME = "p.oxd-userdropdown-name"
    LOGOUT_LINK = "a[href*='auth/logout']"

    # ---------- PIM top navigation tabs ----------
    # Configuration | Employee List | Add Employee | Reports
    TOP_NAV_TAB = ".oxd-topbar-body-nav-tab-item:text-is('{name}')"

    # ---------- left side menu ----------
    SIDE_MENU_SEARCH = "aside input[placeholder='Search']"
    SIDE_MENU_ITEM = "a.oxd-main-menu-item:has(span:text-is('{name}'))"


class SideMenu:
    """Visible names of the left navigation items (screenshot left panel)."""
    ADMIN = "Admin"
    PIM = "PIM"
    LEAVE = "Leave"
    TIME = "Time"
    RECRUITMENT = "Recruitment"
    MY_INFO = "My Info"
    PERFORMANCE = "Performance"
    DASHBOARD = "Dashboard"
    DIRECTORY = "Directory"
    MAINTENANCE = "Maintenance"
    CLAIM = "Claim"
    BUZZ = "Buzz"


class PimTopNav:
    """Visible names of the PIM top navigation tabs."""
    CONFIGURATION = "Configuration"
    EMPLOYEE_LIST = "Employee List"
    ADD_EMPLOYEE = "Add Employee"
    REPORTS = "Reports"


class Messages:
    SUCCESSFULLY_SAVED = "Successfully Saved"
    SUCCESSFULLY_UPDATED = "Successfully Updated"
    SUCCESSFULLY_DELETED = "Successfully Deleted"
    INVALID_CREDENTIALS = "Invalid credentials"
    REQUIRED = "Required"
