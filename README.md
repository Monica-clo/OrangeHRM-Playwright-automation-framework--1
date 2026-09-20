# OrangeHRM – Employee Lifecycle Automation (Playwright + Pytest + k6)

This project automates the **Employee Lifecycle** on https://opensource-demo.orangehrmlive.com/ with exactly **5 end-to-end workflows – 1 negative and 4 positive** – each combining OrangeHRM UI steps with a ReqRes API call whose response is fully validated. Performance testing is a **separate k6 script** (login API + employee creation API) with its own thresholds and report.

| Part of the assessment | Where |
|---|---|
| Part 1 – E2E lifecycle (auth, create, update, API verification, delete) | `tests/e2e/test_employee_workflows.py` |
| Part 2 – Framework (POM, folder structure, config, utilities) | `pages/`, `locators/`, `api/`, `config/`, `utils/` |
| Part 3 – CI/CD (install, run, report, artifacts, parallelisation) | `.github/workflows/ci.yml` (Jenkinsfile as an alternative) |
| Part 4 – Stability (retry, smart waits, screenshots, flaky strategy) | section 8 |
| Part 5 – Performance, bonus (k6, thresholds, report) | `performance/k6/api-performance.js` |
| Part 6 – Reporting (HTML, screenshots/videos, tags, environments) | sections 5 and 6 |

---

## 1. The 5 end-to-end workflows

`tests/e2e/test_employee_workflows.py` is the whole functional suite. Each workflow is self-contained: it logs in, creates its own employee with a unique Employee Id, verifies its own result and cleans up after itself. Any workflow can run alone and a failure in one never cascades into another, so they run in parallel.

| # | Type | Workflow | UI (OrangeHRM) | API (ReqRes) and what is validated |
|---|---|---|---|---|
| 1 | **negative** | Rejected authentication | Valid user + wrong password → `Invalid credentials` is shown, the user stays on the login page, and opening a protected URL still redirects to login (no session was created). | `POST /api/login` without a password → **400**, body `{"error": "Missing password"}`, no `token` in the body. |
| 2 | positive | Create employee | Login → PIM › Add Employee: name, unique Employee Id, profile photo with the orange **+**, login details → Save → toast, Personal Details, avatar, row in the Employee List. | `POST /api/users` with the name read back from the UI → **201**. |
| 3 | positive | Edit employee | Search by Employee Id → update Other Id, Driver's License, Nationality, Marital Status, Gender → reload and verify → change the profile photo and prove the avatar changed. | `PUT /api/users/{id}` → **200**. |
| 4 | positive | Add contact details | Contact Details tab: address, State/Province, Zip, Country, three telephones, unique Work/Other Email → reload and verify every field. | `PATCH /api/users/{id}` → **200**. |
| 5 | positive | Job details, delete & logout | Job Title and Employment Status → reload → check the Employee List columns → delete → `No Records Found` → logout → session is invalid. | `DELETE /api/users/{id}` → **204**, empty body. |

The positive login itself is covered by every positive workflow: the `dashboard` fixture logs in and verifies the Dashboard (URL, header, user menu), and the session-wide `reqres_token` fixture calls `POST /api/login`, validates that response, and hands the bearer token to the API call of workflows 2–5.

### Response validation (`api/validators.py`)

Every API response goes through `validate_response()`. It never accepts a response on the status code alone:

| Check | Example |
|---|---|
| Status code | exactly `201`, `200`, `204`, `400` |
| `Content-Type` | JSON for every response that has a body |
| Response time | below `API_MAX_RESPONSE_MS` (default 5000 ms) |
| JSON schema | `api/schemas.py` (created user, updated user, login success/error) |
| Echoed values | name/job sent from the UI data must come back unchanged |
| Generated fields | `id` is present and not blank |
| Timestamps | `createdAt` / `updatedAt` is a valid ISO-8601 time close to now |
| Negative cases | exact error text (`Missing password`) and **no** `token` in the body |
| Empty body | `DELETE` returns 204 and nothing else |

A failure message names the API, the field, the sent value and the received value.

---

## 2. Performance tests (k6) – separate file

`performance/k6/api-performance.js` is independent of pytest. It load-tests the two transactions from the assignment, using the same request bodies as the E2E workflows (it reads `test_data/api/reqres_test_data.json`):

| Scenario | Request | Per-request checks |
|---|---|---|
| `login` | `POST /api/login` | 200, JSON, token present, response time |
| `create_employee` | `POST /api/users` (unique name per virtual user and iteration) | 201, JSON, `id` generated, name/job echoed, `createdAt` fresh, response time |

**Thresholds** (the run fails with exit code 99 when one is breached; every value can be overridden with `-e NAME=value`):

| Threshold | Default |
|---|---|
| `http_req_duration{endpoint:login}` | p95 < 1500 ms, avg < 1000 ms, max < 4000 ms (`THRESHOLD_LOGIN_*_MS`) |
| `http_req_duration{endpoint:create_employee}` | p95 < 2000 ms, avg < 1200 ms, max < 5000 ms (`THRESHOLD_CREATE_*_MS`) |
| `http_req_failed` (overall and per endpoint) | rate < 1 % (`THRESHOLD_ERROR_RATE`) |
| `checks` (overall and per endpoint) | pass rate > 99 % (`THRESHOLD_CHECK_RATE`) |
| `http_reqs` per endpoint | count > 0 (proves the scenario really ran) |

**Profiles:** `smoke` (default) uses 1 virtual user and about 8 requests, which fits the free ReqRes quota (roughly 40 requests/day and 20/minute on `/api/users`). `load` ramps virtual users for about 75 seconds per scenario and needs a `REQRES_API_KEY` (or your own backend via `REQRES_BASE_URL`).

```bash
mkdir -p reports/performance                       # k6 does not create the report folder itself
k6 run performance/k6/api-performance.js           # smoke profile
k6 run -e PERF_PROFILE=load -e REQRES_API_KEY=<key> performance/k6/api-performance.js
docker run --rm -i -v "$PWD":/work -w /work grafana/k6 run performance/k6/api-performance.js   # without installing k6
./run_tests.sh perf                                # same as the first command (run_tests.bat perf on Windows)
```

**Reports:** `reports/performance/k6-report.html` (verdict, latency table with min/avg/med/p90/p95/p99/max, throughput, failed %, every threshold as PASS/FAIL, HTTP 429 count) and `reports/performance/k6-summary.json` (the full k6 summary).

Install k6: https://grafana.com/docs/k6/latest/set-up/install-k6/

---

## 3. Framework structure

```
orangehrm-playwright-automation/
├── .github/workflows/ci.yml        # CI: E2E matrix (browser x xdist workers), k6 job, Allure report
├── Jenkinsfile                     # Jenkins alternative (Playwright image + k6 image)
├── api/
│   ├── base_client.py              # APIRequestContext wrapper (log, retry on 429, throttle, Allure attachments)
│   ├── reqres_client.py            # ReqRes calls: login, create, PUT, PATCH, DELETE
│   ├── validators.py               # validate_response(): status, headers, time, schema, values, negative checks
│   ├── schemas.py                  # JSON schemas + assert_schema()
│   └── models.py                   # EmployeeSnapshot (row read from the UI, compared with the test data)
├── config/                         # config.yaml + settings.py (every value overridable by an env variable)
├── locators/                       # named locator constants (login, common, PIM)
├── pages/                          # Page Objects (login, dashboard, employee list, profile tabs ...)
├── tests/
│   ├── api/test_reqres_api_contract.py    # API-only contract suite (6 tests, no browser)
│   └── e2e/test_employee_workflows.py     # the 5 workflows (1 negative, 4 positive)
├── performance/k6/api-performance.js      # k6: login + employee creation, thresholds, HTML/JSON report
├── test_data/
│   ├── employees.json / employees.csv     # employee data (the workflows use the first record)
│   ├── employee_profile.json              # personal / contact details
│   ├── api/reqres_test_data.json          # UI negative input + API cases; also read by k6
│   └── images/                            # employee_photo.png (add) / profile_picture.png (edit)
├── tools/                          # collect_evidence.py (commit reports/videos), check_reqres.py (API key check)
├── utils/                          # data reader/models, logger, steps, screen recorder, image helper
├── conftest.py                     # fixtures (browser context, video, trace, ReqRes token, cleanup) + report hooks
├── pytest.ini                      # tags (markers), HTML / JUnit / Allure output
├── setup_and_run.ps1 / setup_and_run.sh   # one-shot: create venv, install, run API + UI + perf
├── run_tests.sh / run_tests.bat
└── requirements.txt
```

---

## 4. Setup

**Prerequisites:** Python 3.10+ (3.12 recommended) and Git. k6 is needed only for the performance test.

### Quickest: the setup script

Creates the virtual environment, installs everything, installs the browser and runs all three suites.

```powershell
# Windows / PowerShell
.\setup_and_run.ps1                 # setup + API + UI + performance
.\setup_and_run.ps1 -Only api       # API contract suite only (no browser)
.\setup_and_run.ps1 -Only ui        # the 5 E2E workflows only
.\setup_and_run.ps1 -Only perf      # k6 only
.\setup_and_run.ps1 -SetupOnly      # install only, run nothing
```
```bash
# macOS / Linux
./setup_and_run.sh                  # setup + API + UI + performance
./setup_and_run.sh api | ui | perf | setup
```

> Keep the project **outside** `Downloads`. Windows Defender locks freshly extracted files
> there, which makes `python -m venv .venv` fail with *Permission denied*.
> If PowerShell blocks the script: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

### Manual setup - Windows
```bat
cd orangehrm-playwright-automation
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m playwright install chromium
```
- **PowerShell:** activate with `.venv\Scripts\Activate.ps1`. If scripts are blocked, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.
- **App Control:** if Windows blocks `pytest.exe`, always use `python -m pytest ...`.

### macOS / Linux
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install --with-deps chromium
```

---

## 5. How to run (execution steps) and the tagging strategy

### The three suites

| # | Suite | Command | Browser? | Duration |
|---|---|---|---|---|
| 1 | **API** – ReqRes contract (6 tests) | `python -m pytest -m api` | no | ~20 s |
| 2 | **UI + API** – the 5 E2E workflows | `python -m pytest -m workflow --browser chromium` | yes | minutes |
| 3 | **Performance** – k6 load test | `k6 run performance/k6/api-performance.js` | no | ~1 min |

The API suite is the fast feedback loop: it validates the endpoint contract on its own
(status, JSON content type, response time, schema, echoed payload, generated ids, fresh
timestamps, error bodies) with no browser and no OrangeHRM session, so a broken contract
is caught in seconds. In CI it gates the slower browser matrix. The E2E workflows check
the same APIs from the other direction – as the mirror of a UI action.

### Tags

Tests carry these tags (pytest markers, enforced by `--strict-markers`):

| Tag | Meaning | Tests |
|---|---|---|
| `api` | added automatically to everything under `tests/api` | the 6 API tests |
| `e2e` | added automatically to everything under `tests/e2e` | workflows 1–5 |
| `workflow` | one of the 5 workflows | 1–5 |
| `positive` | happy path | 2, 3, 4, 5 |
| `negative` | the request must be rejected | 1 |
| `smoke` | fast critical checks | 1, 2 |
| `regression` | extended coverage | 3, 4, 5 |

| Goal | Command |
|---|---|
| API contract suite (no browser) | `python -m pytest -m api` |
| All 5 workflows | `python -m pytest -m workflow` |
| The negative workflow only | `python -m pytest -m negative` |
| The 4 positive workflows | `python -m pytest -m positive --headed` |
| Smoke / regression | `python -m pytest -m smoke` / `python -m pytest -m regression` |
| One workflow | `python -m pytest -k workflow_3 --headed` |
| In parallel (2 workers) | `python -m pytest -m workflow -n 2` |
| Chrome **and** Firefox | `python -m pytest -m workflow --browser chromium --browser firefox -n 2` |
| Retry flaky tests | `python -m pytest -m workflow --reruns 1 --reruns-delay 5` |
| Slow motion, easy-to-watch video | `set SLOW_MO_MS=500` (Windows) or `export SLOW_MO_MS=500`, then run |
| Another environment | `ORANGEHRM_BASE_URL=https://staging.example.com ORANGEHRM_USERNAME=... ORANGEHRM_PASSWORD=... python -m pytest -m workflow` |
| CSV instead of JSON employee data | `DATA_SOURCE=csv python -m pytest -m workflow` |
| **k6 performance test** | `./run_tests.sh perf` or `k6 run performance/k6/api-performance.js` |
| Helper script | `run_tests.bat api` / `run_tests.bat negative` / `./run_tests.sh positive --headed` |
| Everything, from scratch | `.\setup_and_run.ps1` / `./setup_and_run.sh` |

**Environment-based execution:** nothing is hard-coded. `config/config.yaml` holds the defaults and every value is overridden by an environment variable (URL, credentials, browser, data source, timeouts, ReqRes URL and key). CI passes them as environment variables and secrets.

### Environment variables
| Variable | Default | Purpose |
|---|---|---|
| `ORANGEHRM_BASE_URL` | demo site | Environment under test |
| `ORANGEHRM_USERNAME` / `ORANGEHRM_PASSWORD` | `Admin` / `admin123` | Login |
| `BROWSER` | `chromium` | `chromium`, `firefox`, `webkit` or a list such as `chromium,firefox` |
| `CHROMIUM_CHANNEL` / `FIREFOX_CHANNEL` | empty | `chrome`/`msedge` = installed browser; `moz-firefox` = installed Firefox (no video) |
| `DATA_SOURCE` | `json` | `json` or `csv` |
| `REQRES_BASE_URL` / `REQRES_API_KEY` | `https://reqres.in` / empty | ReqRes host and `x-api-key` |
| `REQRES_SKIP_ON_QUOTA` | `false` | Report the API step as *skipped* (not failed) when the ReqRes **daily** quota is used up |
| `REQRES_USERS_MIN_INTERVAL` | `3.2` s | Throttle for `/api/users` (20 requests/minute limit) |
| `API_MAX_RESPONSE_MS` | `5000` | Maximum response time accepted by `validate_response()` |
| `CLEANUP_CREATED_EMPLOYEES` | `true` | Delete employees left behind by failed runs |
| `RECORD_VIDEO` / `VIDEO_CAPTIONS` / `SLOW_MO_MS` / `TRACING` | `true` / `true` / `0` / `retain-on-failure` | Recording and tracing |
| `EXPECT_TIMEOUT` / `DEFAULT_TIMEOUT` | `20000` ms | Increase if the demo site is slow |
| `PERF_PROFILE` and `THRESHOLD_*` | `smoke` | k6 settings, see section 2 |

---

## 6. Reports and evidence

| Artifact | Location |
|---|---|
| HTML report – API suite | `reports/html/api-report.html` |
| HTML report – E2E suite (video and failure screenshot embedded, API logs) | `reports/html/e2e-report.html` |
| HTML report – ad-hoc runs | `reports/html/report.html` |
| k6 performance report | `reports/performance/k6-report.html` (+ `k6-summary.json`) |
| Allure results (UI steps plus API request/response attachments) | `reports/allure-results` – view with `allure serve reports/allure-results` |
| **Videos** (one per workflow, with on-screen step captions) | `reports/videos/<test name>.webm` |
| **Screenshots** on failure, plus avatar before/after | `reports/screenshots/` |
| Playwright traces (on failure) | `reports/traces/*.zip` – open with `python -m playwright show-trace <zip>` |
| Execution log / JUnit XML | `reports/logs/`, `reports/junit/results.xml` |
| **k6 report** | `reports/performance/k6-report.html`, `k6-summary.json` |

`reports/` is overwritten on every run. To commit the evidence the assessment asks for, run `python tools/collect_evidence.py`, then `git add evidence` (it copies the report, videos, screenshots and k6 report into `evidence/run_<date>/`).

---

## 7. CI/CD – `.github/workflows/ci.yml`

| Job | What it does |
|---|---|
| `e2e-tests` | Matrix: **one job per browser** (Chromium, Firefox), each running `pytest -m <tag> -n <workers>` with **xdist parallel workers** and one automatic rerun. Installs dependencies and the browser, publishes the JUnit results, and uploads the HTML report, videos, screenshots, traces and Allure results as an artifact. |
| `performance-tests` | Installs k6 and runs `k6 run performance/k6/api-performance.js`. The thresholds decide pass/fail; `k6-report.html` and `k6-summary.json` are uploaded as an artifact. Runs on the nightly schedule or manually, **not** on every push, because the free ReqRes tier has a small daily quota. |
| `allure-report` | Merges the Allure results of all browser jobs into one report and uploads it (published to GitHub Pages on `main`). |

- **Triggers:** push to `main`/`develop`, pull requests to `main`, a nightly schedule, and a manual run where you choose the suite (`all`, `e2e`, `performance`), the tag, browsers, workers, data source, environment URL and k6 profile.
- **Secrets** (optional): `ORANGEHRM_USERNAME`, `ORANGEHRM_PASSWORD`, `REQRES_API_KEY`.
- **Jenkins:** `Jenkinsfile` has the same two stages (Playwright image, then the `grafana/k6` image) and publishes the same reports.

---

## 8. Test stability and flaky-test strategy

**Implemented in the framework**
| Technique | How |
|---|---|
| Retry logic | `--reruns 1 --reruns-delay 5` (pytest-rerunfailures) in CI; the API client retries HTTP 429 honouring `Retry-After`; a used-up ReqRes *daily* quota is never retried (`--rerun-except=ApiQuotaExceededError`). |
| Smart waiting | No fixed sleeps in tests. Playwright auto-waiting plus `expect()` assertions poll up to `EXPECT_TIMEOUT`; page objects wait for the table, toast or page-ready state; the Personal Details page reloads once when the shared demo renders half a page. |
| Screenshots on failure | `conftest.py` saves a full-page screenshot, embeds it in the HTML report and attaches it to Allure. Video and a Playwright trace are kept as well. |
| Isolation | Unique Employee Ids and emails per run, one browser context per test, no test depends on another, and leftover employees are deleted after a failed run. |
| Clear login failures | If the demo answers `Invalid credentials` for the configured user, the test stops at once and says so instead of timing out on the Dashboard. |

**Detection:** a test that fails and then passes on a rerun is shown as *rerun* in the HTML report and JUnit XML, and Allure lists the earlier attempts as retries. Review these after every nightly run; a test that needs a rerun regularly is flaky even though the build is green.
**Mitigation:** first read the trace and video of the failed attempt, then fix the cause instead of raising retries – replace timing assumptions with a condition to wait for, make the data unique, and remove shared state. Reruns are the safety net for a shared public demo, not the fix.

---

## 9. Key design decisions

- **Exactly 5 workflows (1 negative, 4 positive)**: one place for the lifecycle, no duplicated flows. Each is independent, so they parallelise and can be run alone.
- **Hybrid UI + API**: the UI is the source of truth; the API payloads are built from values read back from the UI, so the assertions link the two layers.
- **Validation as a layer, not as copy-paste**: `validate_response()` keeps the tests short and makes every API call be checked in the same complete way.
- **Data-driven**: employee data in JSON/CSV, API cases and expectations in `reqres_test_data.json`; the same file feeds k6, so the E2E suite and the load test cannot drift apart.
- **Performance separated from functional tests**: k6 is the right tool for load and thresholds; it has its own runner, its own CI job and its own report, and it does not consume the ReqRes quota of the functional runs.
- **Config through environment variables**: the same code runs locally, in GitHub Actions and in Jenkins.
- **ReqRes as the API layer**: the "API-level verification" step is simulated with the public ReqRes API (login, users), fed with the data read from the OrangeHRM UI. It is a shared public service with a small anonymous quota; use `REQRES_API_KEY` for regular runs.

---

## 10. Test data

- **`employees.json` / `.csv`:** `profile_picture` is uploaded when the employee is created and `edit_profile_picture` when it is edited (jpg, png or gif, up to 1 MB). The Employee Id and username get a random suffix at run time because the demo site is shared. The workflows use the first record.
- **`api/reqres_test_data.json`:** `auth_ui` (the wrong password for the negative workflow and the expected message), `auth_apis` (login and the "missing password" case with its expected status and error) and `user_apis` (request bodies, ids and expected status codes for POST / PUT / PATCH / DELETE). To test other values change the JSON, not the code.
- **Dropdown values:** `job_title` and `employment_status` must exist in the demo. If one is missing, the error message lists the available options.

---

## 11. UI locator map (from the application screenshots)

Most form fields are located by their **visible label**, using the `INPUT_BY_LABEL` and `SELECT_BY_LABEL` templates in `common_locators.py`. As a result, locator names read like the UI.

**Add Employee** (screenshots 1–2): `AddEmployeeLocators`
| UI element | Locator name | Selector |
|---|---|---|
| First Name | `FIRST_NAME_INPUT` | `input[name='firstName']` |
| Middle Name | `MIDDLE_NAME_INPUT` | `input[name='middleName']` |
| Last Name | `LAST_NAME_INPUT` | `input[name='lastName']` |
| Employee Id | `EMPLOYEE_ID_INPUT` | input under the label "Employee Id" |
| Orange **+** on the avatar (opens the file chooser) | `ADD_PROFILE_PICTURE_BUTTON` | `button.employee-image-action` |
| Hidden photo file input (fallback) | `PROFILE_PICTURE_FILE_INPUT` | `input[type='file']` |
| "Accepts jpg, .png, .gif up to 1MB" hint | `PROFILE_PICTURE_HINT` | text locator |
| Avatar preview | `PROFILE_PICTURE_PREVIEW` | `img.employee-image` |
| Create Login Details toggle | `CREATE_LOGIN_DETAILS_TOGGLE` | `div.oxd-switch-wrapper span.oxd-switch-input` |
| Username | `USERNAME_INPUT` | input under the label "Username" |
| Status Enabled / Disabled | `STATUS_ENABLED_RADIO` / `STATUS_DISABLED_RADIO` | the label "Enabled" / "Disabled" |
| Password / Confirm Password | `PASSWORD_INPUT` / `CONFIRM_PASSWORD_INPUT` | input under the matching label |
| Cancel / Save | `CANCEL_BUTTON` / `SAVE_BUTTON` | `button:has-text('Cancel')` / `button[type='submit']` |

**Personal Details** (screenshots 3–4): `PersonalDetailsLocators`
| UI element | Locator name |
|---|---|
| Name above avatar ("Monica N") | `EMPLOYEE_NAME_HEADER` |
| Employee Id / Other Id | `EMPLOYEE_ID_INPUT` / `OTHER_ID_INPUT` |
| Driver's License Number / License Expiry Date | `DRIVERS_LICENSE_NUMBER_INPUT` / `LICENSE_EXPIRY_DATE_INPUT` |
| Nationality / Marital Status | `NATIONALITY_DROPDOWN` / `MARITAL_STATUS_DROPDOWN` |
| Date of Birth | `DATE_OF_BIRTH_INPUT` |
| Gender Male / Female | `GENDER_MALE_RADIO` / `GENDER_FEMALE_RADIO` |
| Save (Personal Details) | `PERSONAL_DETAILS_SAVE_BUTTON` |
| Blood Type / Test_Field / Save (Custom Fields) | `BLOOD_TYPE_DROPDOWN` / `TEST_FIELD_INPUT` / `CUSTOM_FIELDS_SAVE_BUTTON` |
| Left tabs (Personal Details, Contact Details, Job …) | `TAB_*` constants |

**Change Profile Picture** (opened by clicking the avatar): `ChangeProfilePictureLocators`
| UI element | Locator name |
|---|---|
| Avatar in the left panel (click to open the page) | `AVATAR_LINK` / `PROFILE_PICTURE` |
| "Change Profile Picture" title | `PAGE_TITLE` |
| Photo file input / preview | `PHOTO_FILE_INPUT` / `PHOTO_PREVIEW` |
| Save | `SAVE_BUTTON` |

**Contact Details** (screenshot 5): `ContactDetailsLocators`
| UI element | Locator name |
|---|---|
| Street 1 / Street 2 / City | `STREET_1_INPUT` / `STREET_2_INPUT` / `CITY_INPUT` |
| State/Province / Zip/Postal Code / Country | `STATE_PROVINCE_INPUT` / `ZIP_POSTAL_CODE_INPUT` / `COUNTRY_DROPDOWN` |
| Telephone: Home / Mobile / Work | `HOME_TELEPHONE_INPUT` / `MOBILE_INPUT` / `WORK_TELEPHONE_INPUT` |
| Work Email / Other Email | `WORK_EMAIL_INPUT` / `OTHER_EMAIL_INPUT` |

**Job tab and Employee List** (step 3)
| UI element | Locator name |
|---|---|
| Job Title / Employment Status dropdowns | `JobDetailsLocators.JOB_TITLE_DROPDOWN` / `EMPLOYMENT_STATUS_DROPDOWN` |
| Employee Id search box / Search button | `EmployeeListLocators.EMPLOYEE_ID_INPUT` / `SEARCH_BUTTON` |
| Result rows / cells / edit icon | `TABLE_ROWS` / `ROW_CELLS` / `ROW_EDIT_ICON` |

**Common** (every page): `CommonLocators`. This covers the top bar header (`MODULE_HEADER`), the user menu (`USER_DROPDOWN`), the side menu (`SIDE_MENU_ITEM`), the PIM tabs (`TOP_NAV_TAB`), toasts (`TOAST_MESSAGE`) and dropdown options (`DROPDOWN_OPTION`).

---

## 12. Dependencies

| Package | Purpose |
|---|---|
| `playwright` | Browser automation, API requests (`APIRequestContext`), video and tracing |
| `pytest` | Test runner |
| `pytest-playwright` | Browser fixtures and CLI options (`--browser`, `--headed`, `--slowmo`, `--browser-channel`) |
| `pytest-html` | Self-contained HTML report |
| `allure-pytest` | Allure results with steps and API attachments |
| `pytest-rerunfailures` | Retries for runs against the shared demo sites |
| `pytest-xdist` | Parallel execution (`-n 2`) |
| `jsonschema` | Validating API responses against contracts |
| `PyYAML` | Reading the configuration file |
| `k6` (separate tool) | Performance test in `performance/k6/` |

---

## 13. Troubleshooting

| Symptom | Fix |
|---|---|
| `Login rejected with 'Invalid credentials'` for `Admin` | The public demo's password is sometimes changed or reset by other users. Check the current credentials on the demo login page and set `ORANGEHRM_USERNAME` / `ORANGEHRM_PASSWORD`. |
| `pytest.exe ... blocked by Application Control policy` | Use `python -m pytest`. |
| `Could not open requirements file` | You are in the wrong folder. `cd` into the folder that contains `requirements.txt`. |
| ReqRes returns **401** or **403** | ReqRes may require a key. Create a free one at app.reqres.in and set `REQRES_API_KEY` (`python tools/check_reqres.py` tests it). |
| ReqRes returns **429** "demo limit of 40 requests/day" | The anonymous daily quota is used up (resets at midnight UTC), so the client stops immediately. Set `REQRES_API_KEY`, or `REQRES_SKIP_ON_QUOTA=true` to report the API step as skipped. |
| k6: `could not write report ... no such file or directory` | Create the folder first: `mkdir -p reports/performance` (`run_tests.sh perf` and CI do it). |
| k6: many `HTTP 429` and failed thresholds | The free ReqRes tier is rate-limited. Use the `smoke` profile or set `REQRES_API_KEY`. |
| "Personal Details title should be visible" under parallel load | The demo site is slow. Use fewer workers (`-n 2`), raise `EXPECT_TIMEOUT=40000`, or add `--reruns 1`. |
| `Option 'QA Engineer' is not available` | The shared demo data changed. Use one of the options listed in the error. |
| Debugging a UI failure | `python -m playwright show-trace reports/traces/<test>.zip` |
