pipeline {
    agent any
    options {
        disableConcurrentBuilds()
        ansiColor('xterm')
    }
    environment {
        // Replace with your actual AOSP manifest URL and branch
        AOSP_MANIFEST_URL = 'https://github.com/AfterlifeOS/afterlife_manifest.git'
        AOSP_MANIFEST_BRANCH = '16'
        // Setting up RBE (this value can be changed, adaptation for your OS)
        USE_RBE = '1'
        RBE_DIR = '/srv/rbe'
        RBE_re_proxy = '/srv/rbe/reproxy'
        RBE_service = 'localhost:8085'
        RBE_service_no_auth = 'true'
        RBE_service_no_security = 'true'
        RBE_use_rpc_credentials = 'false'
        RBE_use_application_default_credentials = 'false'
        RBE_CXX_EXEC_STRATEGY = 'remote_local_fallback'
        RBE_JAVAC_EXEC_STRATEGY = 'remote_local_fallback'
        RBE_R8_EXEC_STRATEGY = 'remote_local_fallback'
        RBE_D8_EXEC_STRATEGY = 'remote_local_fallback'
        RBE_CXX = '1'
        RBE_JAVAC = '1'
        RBE_R8 = '1'
        RBE_D8 = '1'
        RBE_SIGNAPK = '1'
        RBE_METALAVA = '1'
        RBE_LINT = '1'
        RBE_JAR = '1'
        RBE_ZIP = '1'
        NINJA_REMOTE_NUM_JOBS = '512'
        RBE_cas_concurrency = '2000'
        RBE_use_unified_uploads = 'true'
        RBE_use_unified_downloads = 'true'
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
                    sh """
                        chmod -R +x builder/
                        git config --global user.name "HinohArata"
                        git config --global user.email "161218134+HinohArata@users.noreply.github.com"
                        ./builder/initialize.sh
                    """
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
                        ./builder/upload.sh "${params.DEVICE}"
                    """
                }
            }
        }
    }
}
