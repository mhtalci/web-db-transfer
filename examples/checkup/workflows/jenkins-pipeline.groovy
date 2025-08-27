// Jenkins Pipeline with Codebase Checkup
// Save as Jenkinsfile in your project root

pipeline {
    agent any
    
    environment {
        PYTHON_VERSION = '3.9'
        PIP_CACHE_DIR = "${WORKSPACE}/.pip-cache"
        CHECKUP_REPORTS_DIR = "${WORKSPACE}/checkup-reports"
    }
    
    options {
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 30, unit: 'MINUTES')
        timestamps()
    }
    
    triggers {
        // Poll SCM every 5 minutes for changes
        pollSCM('H/5 * * * *')
        
        // Weekly quality check
        cron('H 2 * * 1')
    }
    
    stages {
        stage('Setup') {
            steps {
                echo 'Setting up Python environment...'
                sh '''
                    python${PYTHON_VERSION} -m venv venv
                    . venv/bin/activate
                    pip install --upgrade pip
                    pip install migration-assistant[checkup]
                '''
            }
        }
        
        stage('Install Dependencies') {
            steps {
                sh '''
                    . venv/bin/activate
                    if [ -f requirements.txt ]; then
                        pip install -r requirements.txt
                    fi
                    if [ -f pyproject.toml ]; then
                        pip install -e .
                    fi
                '''
            }
        }
        
        stage('Unit Tests') {
            steps {
                sh '''
                    . venv/bin/activate
                    python -m pytest tests/ \
                        --cov=src/ \
                        --cov-report=xml \
                        --cov-report=html \
                        --junitxml=test-results.xml
                '''
            }
            post {
                always {
                    publishTestResults testResultsPattern: 'test-results.xml'
                    publishCoverageResults([
                        [
                            path: 'coverage.xml',
                            type: 'COBERTURA'
                        ]
                    ])
                }
            }
        }
        
        stage('Code Quality Analysis') {
            parallel {
                stage('Checkup Analysis') {
                    steps {
                        sh '''
                            . venv/bin/activate
                            mkdir -p ${CHECKUP_REPORTS_DIR}
                            migration-assistant checkup analyze \
                                --config examples/checkup/ci-checkup.toml \
                                --report-json \
                                --report-xml \
                                --output-dir ${CHECKUP_REPORTS_DIR}
                        '''
                    }
                }
                
                stage('Security Scan') {
                    steps {
                        sh '''
                            . venv/bin/activate
                            pip install bandit safety
                            bandit -r src/ -f json -o bandit-report.json || true
                            safety check --json --output safety-report.json || true
                        '''
                    }
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'checkup-reports/**/*', allowEmptyArchive: true
                    archiveArtifacts artifacts: '*-report.json', allowEmptyArchive: true
                }
            }
        }
        
        stage('Quality Gate') {
            steps {
                script {
                    def qualityGatePassed = sh(
                        script: '''
                            . venv/bin/activate
                            python -c "
import json
import sys
import glob

report_files = glob.glob('${CHECKUP_REPORTS_DIR}/checkup-*.json')
if not report_files:
    print('No quality report found')
    sys.exit(1)
    
with open(report_files[0]) as f:
    report = json.load(f)

critical_issues = sum(1 for issue in report.get('quality_issues', []) 
                     if issue.get('severity') == 'critical')

quality_score = report['metrics']['quality_score']

print(f'Quality score: {quality_score}/100')
print(f'Critical issues: {critical_issues}')

if critical_issues > 0:
    print('Quality gate failed: Critical issues found')
    sys.exit(1)

if quality_score < 70:
    print('Quality gate failed: Quality score too low')
    sys.exit(1)
    
print('Quality gate passed')
"
                        ''',
                        returnStatus: true
                    )
                    
                    if (qualityGatePassed != 0) {
                        currentBuild.result = 'UNSTABLE'
                        error('Quality gate failed')
                    }
                }
            }
        }
        
        stage('Deploy') {
            when {
                anyOf {
                    branch 'main'
                    branch 'master'
                }
            }
            parallel {
                stage('Format Code') {
                    when {
                        anyOf {
                            triggeredBy 'UserIdCause'
                            triggeredBy 'TimerTrigger'
                        }
                    }
                    steps {
                        sh '''
                            . venv/bin/activate
                            git config --global user.email "jenkins@example.com"
                            git config --global user.name "Jenkins CI"
                            
                            migration-assistant checkup format \
                                --config examples/checkup/development-checkup.toml \
                                --backup
                            
                            if [ -n "$(git status --porcelain)" ]; then
                                git add -A
                                git commit -m "Auto-format code with checkup [skip ci]"
                                git push origin HEAD:${BRANCH_NAME}
                            else
                                echo "No formatting changes needed"
                            fi
                        '''
                    }
                }
                
                stage('Quality Dashboard') {
                    steps {
                        sh '''
                            . venv/bin/activate
                            mkdir -p quality-dashboard
                            migration-assistant checkup run \
                                --config examples/checkup/team-checkup.toml \
                                --report-html \
                                --report-json \
                                --output-dir quality-dashboard
                        '''
                        
                        publishHTML([
                            allowMissing: false,
                            alwaysLinkToLastBuild: true,
                            keepAll: true,
                            reportDir: 'quality-dashboard',
                            reportFiles: '*.html',
                            reportName: 'Quality Dashboard'
                        ])
                    }
                }
            }
        }
    }
    
    post {
        always {
            cleanWs()
        }
        
        success {
            script {
                if (env.BRANCH_NAME == 'main' || env.BRANCH_NAME == 'master') {
                    emailext (
                        subject: "✅ Quality Check Passed: ${env.JOB_NAME} - ${env.BUILD_NUMBER}",
                        body: """
                        <h2>Code Quality Check Passed</h2>
                        <p><strong>Project:</strong> ${env.JOB_NAME}</p>
                        <p><strong>Build:</strong> ${env.BUILD_NUMBER}</p>
                        <p><strong>Branch:</strong> ${env.BRANCH_NAME}</p>
                        <p><strong>Build URL:</strong> <a href="${env.BUILD_URL}">${env.BUILD_URL}</a></p>
                        
                        <h3>Quality Reports</h3>
                        <p>Quality dashboard: <a href="${env.BUILD_URL}Quality_Dashboard/">View Dashboard</a></p>
                        """,
                        to: "${env.CHANGE_AUTHOR_EMAIL}",
                        mimeType: 'text/html'
                    )
                }
            }
        }
        
        failure {
            emailext (
                subject: "❌ Quality Check Failed: ${env.JOB_NAME} - ${env.BUILD_NUMBER}",
                body: """
                <h2>Code Quality Check Failed</h2>
                <p><strong>Project:</strong> ${env.JOB_NAME}</p>
                <p><strong>Build:</strong> ${env.BUILD_NUMBER}</p>
                <p><strong>Branch:</strong> ${env.BRANCH_NAME}</p>
                <p><strong>Build URL:</strong> <a href="${env.BUILD_URL}">${env.BUILD_URL}</a></p>
                
                <h3>Failure Details</h3>
                <p>Please check the build logs and quality reports for details.</p>
                <p>Console Output: <a href="${env.BUILD_URL}console">View Logs</a></p>
                """,
                to: "${env.CHANGE_AUTHOR_EMAIL}",
                mimeType: 'text/html'
            )
        }
        
        unstable {
            emailext (
                subject: "⚠️ Quality Issues Found: ${env.JOB_NAME} - ${env.BUILD_NUMBER}",
                body: """
                <h2>Code Quality Issues Found</h2>
                <p><strong>Project:</strong> ${env.JOB_NAME}</p>
                <p><strong>Build:</strong> ${env.BUILD_NUMBER}</p>
                <p><strong>Branch:</strong> ${env.BRANCH_NAME}</p>
                <p><strong>Build URL:</strong> <a href="${env.BUILD_URL}">${env.BUILD_URL}</a></p>
                
                <h3>Quality Issues</h3>
                <p>The build completed but quality issues were found. Please review the quality reports.</p>
                <p>Quality dashboard: <a href="${env.BUILD_URL}Quality_Dashboard/">View Dashboard</a></p>
                """,
                to: "${env.CHANGE_AUTHOR_EMAIL}",
                mimeType: 'text/html'
            )
        }
    }
}