// Jenkins declarative pipeline (alternative to GitHub Actions).
// Plugins: Pipeline, Docker Pipeline, JUnit, HTML Publisher.
// Credentials: "Username with password" id 'orangehrm-credentials'
//              (optional) "Secret text" id 'reqres-api-key'
pipeline {
    agent none

    parameters {
        choice(name: 'SUITE', choices: ['all', 'e2e', 'performance'], description: 'Suites to run')
        choice(name: 'MARKER', choices: ['workflow', 'positive', 'negative', 'smoke', 'regression'], description: 'E2E tag to execute')
        string(name: 'BROWSERS', defaultValue: 'chromium firefox', description: 'Browsers for the E2E workflows (space separated)')
        choice(name: 'WORKERS', choices: ['2', '1', '4', 'auto'], description: 'Parallel workers (pytest-xdist)')
        choice(name: 'DATA_SOURCE', choices: ['json', 'csv'], description: 'Employee test data source')
        string(name: 'ORANGEHRM_BASE_URL', defaultValue: '', description: 'OrangeHRM environment URL (empty = config/config.yaml)')
        choice(name: 'PERF_PROFILE', choices: ['smoke', 'load'], description: 'k6 profile (load needs a ReqRes API key)')
    }

    triggers { cron('H 2 * * *') }

    options {
        timeout(time: 60, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    stages {
        stage('E2E workflows (UI + API)') {
            when { expression { params.SUITE in ['all', 'e2e'] } }
            agent {
                docker {
                    // Keep this tag equal to the playwright version in requirements.txt
                    image 'mcr.microsoft.com/playwright/python:v1.63.0-noble'
                    args '--ipc=host'
                }
            }
            environment {
                ORANGEHRM = credentials('orangehrm-credentials')
                ORANGEHRM_USERNAME = "${ORANGEHRM_USR}"
                ORANGEHRM_PASSWORD = "${ORANGEHRM_PSW}"
                DATA_SOURCE = "${params.DATA_SOURCE}"
                ORANGEHRM_BASE_URL = "${params.ORANGEHRM_BASE_URL}"
                HOME = "${WORKSPACE}"
            }
            steps {
                sh 'python -m pip install --user -r requirements.txt'
                catchError(buildResult: 'UNSTABLE', stageResult: 'FAILURE') {
                    sh '''BROWSER_ARGS=""; for b in $BROWSERS; do BROWSER_ARGS="$BROWSER_ARGS --browser $b"; done
                          python -m pytest -m "$MARKER" $BROWSER_ARGS -n "$WORKERS" --reruns 1 --reruns-delay 5 \
                          --html=reports/html/e2e-report.html \
                          --junitxml=reports/junit/e2e-results.xml'''
                }
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'reports/junit/*.xml'
                    publishHTML(target: [
                        reportDir: 'reports/html', reportFiles: 'e2e-report.html',
                        reportName: 'E2E HTML Report', keepAll: true,
                        alwaysLinkToLastBuild: true, allowMissing: true
                    ])
                    archiveArtifacts artifacts: 'reports/**', allowEmptyArchive: true
                }
            }
        }

        stage('Performance (k6)') {
            when { expression { params.SUITE in ['all', 'performance'] } }
            agent {
                docker {
                    image 'grafana/k6:latest'
                    args '--entrypoint=""'
                }
            }
            environment {
                PERF_PROFILE = "${params.PERF_PROFILE}"
                REQRES_API_KEY = credentials('reqres-api-key')   // remove this line if you have no key
            }
            steps {
                catchError(buildResult: 'UNSTABLE', stageResult: 'FAILURE') {
                    sh '''mkdir -p reports/performance
                          k6 run performance/k6/api-performance.js'''
                }
            }
            post {
                always {
                    publishHTML(target: [
                        reportDir: 'reports/performance', reportFiles: 'k6-report.html',
                        reportName: 'k6 Performance Report', keepAll: true,
                        alwaysLinkToLastBuild: true, allowMissing: true
                    ])
                    archiveArtifacts artifacts: 'reports/performance/**', allowEmptyArchive: true
                }
            }
        }
    }
}
