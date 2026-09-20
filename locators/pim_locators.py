"""PIM module locators - named after the fields visible in the screenshots.

Screenshot 1 & 2 -> AddEmployeeLocators       (/pim/addEmployee)
Screenshot 3 & 4 -> PersonalDetailsLocators   (/pim/viewPersonalDetails/empNumber/<n>)
Screenshot 5     -> ContactDetailsLocators    (/pim/contactDetails/empNumber/<n>)
Scenario step 3  -> EmployeeListLocators, JobDetailsLocators
"""
from locators.common_locators import CommonLocators as C

_input = C.INPUT_BY_LABEL.format
_select = C.SELECT_BY_LABEL.format
_radio = C.RADIO_LABEL.format
_radio_input = C.RADIO_INPUT.format


class AddEmployeeLocators:
    """Screenshots 1 & 2 - 'Add Employee' form."""
    PAGE_TITLE = "h6.orangehrm-main-title:text-is('Add Employee')"

    # Employee Full Name*
    FIRST_NAME_INPUT = "input[name='firstName']"
    MIDDLE_NAME_INPUT = "input[name='middleName']"
    LAST_NAME_INPUT = "input[name='lastName']"

    # Employee Id (auto-filled, e.g. 0465)
    EMPLOYEE_ID_INPUT = _input(label="Employee Id")

    # Profile picture: round avatar + orange '+' button (opens the file chooser)
    ADD_PROFILE_PICTURE_BUTTON = "button.employee-image-action, div.orangehrm-employee-image button"
    PROFILE_PICTURE_FILE_INPUT = "input[type='file']"          # hidden input behind the '+' button
    PROFILE_PICTURE_PREVIEW = "img.employee-image"
    PROFILE_PICTURE_HINT = "text=Accepts jpg, .png, .gif up to 1MB"

    # Create Login Details toggle
    CREATE_LOGIN_DETAILS_TOGGLE = "div.oxd-switch-wrapper span.oxd-switch-input"
    CREATE_LOGIN_DETAILS_CHECKBOX = "div.oxd-switch-wrapper input[type='checkbox']"

    # Login details (visible after the toggle is ON - screenshot 2)
    USERNAME_INPUT = _input(label="Username")
    PASSWORD_INPUT = _input(label="Password")
    CONFIRM_PASSWORD_INPUT = _input(label="Confirm Password")
    STATUS_ENABLED_RADIO = _radio(label="Enabled")
    STATUS_DISABLED_RADIO = _radio(label="Disabled")
    STATUS_RADIO_INPUT = C.RADIO_INPUT          # .format(label="Enabled")
    PASSWORD_STRENGTH_CHIP = ".orangehrm-password-chip"    # "Weak" / "Strong"

    # Buttons
    CANCEL_BUTTON = "button:has-text('Cancel')"
    SAVE_BUTTON = "button[type='submit']"


class EmployeeListLocators:
    """PIM > Employee List (search + results table)."""
    FILTER_TITLE = "h5.oxd-table-filter-title"         # "Employee Information"
    EMPLOYEE_NAME_INPUT = _input(label="Employee Name")
    EMPLOYEE_ID_INPUT = _input(label="Employee Id")
    EMPLOYMENT_STATUS_DROPDOWN = _select(label="Employment Status")
    INCLUDE_DROPDOWN = _select(label="Include")
    SUPERVISOR_NAME_INPUT = _input(label="Supervisor Name")
    JOB_TITLE_DROPDOWN = _select(label="Job Title")
    SUB_UNIT_DROPDOWN = _select(label="Sub Unit")
    SEARCH_BUTTON = "button[type='submit']"
    RESET_BUTTON = "button:has-text('Reset')"

    # Results table
    RECORDS_FOUND_PATTERN = r"\((\d+)\) Records? Found"
    NO_RECORDS_FOUND_TEXT = "No Records Found"
    TABLE_LOADER = "div.oxd-table-loader"
    TABLE_HEADER_CELLS = "div.oxd-table-header div.oxd-table-th"
    TABLE_ROWS = "div.oxd-table-body div.oxd-table-card"
    ROW_CELLS = "div.oxd-table-cell"
    ROW_EDIT_ICON = "i.bi-pencil-fill"
    ROW_DELETE_ICON = "i.bi-trash"
    CONFIRM_DELETE_BUTTON = "button:has-text('Yes, Delete')"

    # Column headers
    COL_ID = "Id"
    COL_FIRST_MIDDLE_NAME = "First (& Middle) Name"
    COL_LAST_NAME = "Last Name"
    COL_JOB_TITLE = "Job Title"
    COL_EMPLOYMENT_STATUS = "Employment Status"


class EmployeeProfileLocators:
    """Left-hand panel shared by every employee profile tab (screenshots 3-5)."""
    EMPLOYEE_NAME_HEADER = "div.orangehrm-edit-employee-name h6"   # "Monica N"
    # Left-panel avatar = first employee image on the page (the Change Profile Picture
    # page also shows a second one - the upload preview).
    PROFILE_PICTURE = "img.employee-image >> nth=0"

    # Tab names (left menu under the avatar)
    TAB_PERSONAL_DETAILS = "Personal Details"
    TAB_CONTACT_DETAILS = "Contact Details"
    TAB_EMERGENCY_CONTACTS = "Emergency Contacts"
    TAB_DEPENDENTS = "Dependents"
    TAB_IMMIGRATION = "Immigration"
    TAB_JOB = "Job"
    TAB_SALARY = "Salary"
    TAB_REPORT_TO = "Report-to"
    TAB_QUALIFICATIONS = "Qualifications"
    TAB_MEMBERSHIPS = "Memberships"

    # First form on each tab owns the main Save button
    MAIN_FORM_SAVE_BUTTON = "form >> nth=0 >> button[type='submit']"


class ChangeProfilePictureLocators(EmployeeProfileLocators):
    """'Change Profile Picture' page - opened by clicking the avatar on any profile tab
    (/pim/viewPhotograph/empNumber/<n>)."""
    PAGE_TITLE = "h6.orangehrm-main-title:text-is('Change Profile Picture')"
    AVATAR_LINK = "img.employee-image >> nth=0"                # clickable avatar (left panel)
    PHOTO_FILE_INPUT = "input[type='file']"
    PHOTO_PREVIEW = "img.employee-image >> nth=-1"             # preview inside the upload form
    SAVE_BUTTON = "button[type='submit']"


class PersonalDetailsLocators(EmployeeProfileLocators):
    """Screenshots 3 & 4 - Personal Details tab."""
    PAGE_TITLE = "h6.orangehrm-main-title:text-is('Personal Details')"

    FIRST_NAME_INPUT = "input[name='firstName']"
    MIDDLE_NAME_INPUT = "input[name='middleName']"
    LAST_NAME_INPUT = "input[name='lastName']"
    EMPLOYEE_ID_INPUT = _input(label="Employee Id")
    OTHER_ID_INPUT = _input(label="Other Id")
    DRIVERS_LICENSE_NUMBER_INPUT = _input(label="Driver's License Number")
    LICENSE_EXPIRY_DATE_INPUT = _input(label="License Expiry Date")
    NATIONALITY_DROPDOWN = _select(label="Nationality")
    MARITAL_STATUS_DROPDOWN = _select(label="Marital Status")
    DATE_OF_BIRTH_INPUT = _input(label="Date of Birth")
    GENDER_MALE_RADIO = _radio(label="Male")
    GENDER_FEMALE_RADIO = _radio(label="Female")
    GENDER_RADIO_INPUT = C.RADIO_INPUT          # .format(label="Female")
    PERSONAL_DETAILS_SAVE_BUTTON = "form >> nth=0 >> button[type='submit']"

    # Custom Fields section (screenshot 4)
    CUSTOM_FIELDS_TITLE = "h6:text-is('Custom Fields')"
    BLOOD_TYPE_DROPDOWN = _select(label="Blood Type")
    TEST_FIELD_INPUT = _input(label="Test_Field")
    CUSTOM_FIELDS_SAVE_BUTTON = "form >> nth=1 >> button[type='submit']"


class ContactDetailsLocators(EmployeeProfileLocators):
    """Screenshot 5 - Contact Details tab."""
    PAGE_TITLE = "h6.orangehrm-main-title:text-is('Contact Details')"

    # Address
    STREET_1_INPUT = _input(label="Street 1")
    STREET_2_INPUT = _input(label="Street 2")
    CITY_INPUT = _input(label="City")
    STATE_PROVINCE_INPUT = _input(label="State/Province")
    ZIP_POSTAL_CODE_INPUT = _input(label="Zip/Postal Code")
    COUNTRY_DROPDOWN = _select(label="Country")

    # Telephone
    HOME_TELEPHONE_INPUT = _input(label="Home")
    MOBILE_INPUT = _input(label="Mobile")
    WORK_TELEPHONE_INPUT = _input(label="Work")

    # Email
    WORK_EMAIL_INPUT = _input(label="Work Email")
    OTHER_EMAIL_INPUT = _input(label="Other Email")

    SAVE_BUTTON = "form >> nth=0 >> button[type='submit']"


class JobDetailsLocators(EmployeeProfileLocators):
    """Job tab - used in scenario step 3 (update Job Title & Employment Status)."""
    PAGE_TITLE = "h6.orangehrm-main-title:text-is('Job Details')"

    JOINED_DATE_INPUT = _input(label="Joined Date")
    JOB_TITLE_DROPDOWN = _select(label="Job Title")
    JOB_CATEGORY_DROPDOWN = _select(label="Job Category")
    SUB_UNIT_DROPDOWN = _select(label="Sub Unit")
    LOCATION_DROPDOWN = _select(label="Location")
    EMPLOYMENT_STATUS_DROPDOWN = _select(label="Employment Status")
    SAVE_BUTTON = "form >> nth=0 >> button[type='submit']"
