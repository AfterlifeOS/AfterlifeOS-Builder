pipeline {
    agent any
    options {
        disableConcurrentBuilds()
    }
    environment {
        // Replace with your actual AOSP manifest URL and branch
        AOSP_MANIFEST_URL = 'https://github.com/AfterlifeOS/afterlife_manifest.git'
        AOSP_MANIFEST_BRANCH = '16'
    }
    parameters {
        string(name: 'DEVICE', defaultValue: 'walleye', description: 'Device name (e.g., walleye)')
        choice(name: 'RELEASETYPE', choices: ['user', 'userdebug', 'eng'], description: 'Build release type')
        string(name: 'LOCAL_MANIFEST_URL', defaultValue: '', description: 'URL to local_manifest.xml (optional)')
    }
    stages {
        stage('Initializing') {
            steps {
                script {
                    sh 'git config --global user.name "HinohArata"'
                    sh 'git config --global user.email "mmgcntk@gmail.com"'
                    sh './builder/initialize.sh'
                }
            }
        }
        stage('Syncing Source') {
            steps {
                script {
                    sh """
                        ./builder/sync.sh "${params.LOCAL_MANIFEST_URL}"
                    """
                }
            }
        }
        stage('Building') {
            steps {
                script {
                    sh """
                        ./builder/build.sh \
                        "${params.DEVICE}" \
                        "${params.RELEASETYPE}"
                    """
                }
            }
        }
        stage('Uploading Build') {
            steps {
                script {
                    sh """
                        ./builder/upload.sh \
                        "${params.DEVICE}" \
                        "${params.RELEASETYPE}"
                    """
                }
            }
        }
    }
}
