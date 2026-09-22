pipeline {
    agent any

    parameters {
        choice(name: 'SUITE',   choices: ['all', 'api', 'e2e', 'performance'], description: 'Suites to run')
        choice(name: 'MARKER',  choices: ['workflow', 'positive', 'negative', 'smoke', 'regression'], description: 'E2E tag')
        choice(name: 'BROWSER', choices: ['chromium', 'firefox'], description: 'Browser for the E2E workflows')
        choice(name: 'WORKERS', choices: ['2', '1', '4', 'auto'], description: 'Parallel workers (pytest-xdist)')
        choice(name: 'DATA_SOURCE', choices: ['json', 'csv'], description: 'Employee test data source')
        string(name: 'ORANGEHRM_BASE_URL', defaultValue: '', description: 'OrangeHRM URL (empty = config.yaml)')
        choice(name: 'PERF_PROFILE', choices: ['smoke', 'load'], description: 'k6 profile')
    }

    triggers { cron('H 2 * * *') }

    options {
        timeout(time: 60, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
        timestamps()
    }

    environment {
        VENV                 = "${WORKSPACE}/.venv"
        REQRES_SKIP_ON_QUOTA = 'true'
        DATA_SOURCE          = "${params.DATA_SOURCE}"
        ORANGEHRM_BASE_URL   = "${params.ORANGEHRM_BASE_URL}"
    }

    stages {

        stage('Setup') {
            steps {
                sh '''
                    python3 -m venv "$VENV"
                    "$VENV/bin/pip" install --upgrade pip --quiet
                    "$VENV/bin/pip" install -r requirements.txt --quiet
                    mkdir -p reports/html reports/junit reports/performance
                    "$VENV/bin/python" -m pytest --collect-only -q | tail -3
                '''
            }
        }

        stage('API contract tests') {
            when { expression { params.SUITE in ['all', 'api'] } }
            steps {
                catchError(buildResult: 'UNSTABLE', stageResult: 'FAILURE') {
                    sh '"$VENV/bin/python" -m pytest -m api --html=reports/html/api-report.html --self-contained-html --junitxml=reports/junit/api-results.xml'
                }
            }
        }

        stage('E2E workflows (UI + API)') {
            when { expression { params.SUITE in ['all', 'e2e'] } }
            environment {
                ORANGEHRM          = credentials('orangehrm-credentials')
                ORANGEHRM_USERNAME = "${ORANGEHRM_USR}"
                ORANGEHRM_PASSWORD = "${ORANGEHRM_PSW}"
            }
            steps {
                sh '"$VENV/bin/python" -m playwright install ${BROWSER}'
                catchError(buildResult: 'UNSTABLE', stageResult: 'FAILURE') {
                    sh '"$VENV/bin/python" -m pytest -m "$MARKER" --browser "$BROWSER" -n "$WORKERS" --reruns 1 --reruns-delay 5 --html=reports/html/e2e-report.html --self-contained-html --junitxml=reports/junit/e2e-results.xml'
                }
            }
        }

        stage('Performance (k6)') {
            when { expression { params.SUITE in ['all', 'performance'] } }
            environment { PERF_PROFILE = "${params.PERF_PROFILE}" }
            steps {
                catchError(buildResult: 'UNSTABLE', stageResult: 'FAILURE') {
                    sh 'mkdir -p reports/performance && k6 run performance/k6/api-performance.js'
                }
            }
        }
    }

    post {
        always {
            junit allowEmptyResults: true, testResults: 'reports/junit/*.xml'
            publishHTML(target: [reportDir: 'reports/html', reportFiles: 'api-report.html', reportName: 'API HTML Report', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
            publishHTML(target: [reportDir: 'reports/html', reportFiles: 'e2e-report.html', reportName: 'E2E HTML Report', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
            publishHTML(target: [reportDir: 'reports/performance', reportFiles: 'k6-report.html', reportName: 'k6 Performance Report', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
            archiveArtifacts artifacts: 'reports/**', allowEmptyArchive: true
        }
    }
}
