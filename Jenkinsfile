pipeline {
    agent any
    options {
        disableConcurrentBuilds()
        ansiColor('xterm')
    }
    parameters {
        string(name: 'DEVICE', defaultValue: 'walleye', description: 'Device name (e.g., walleye)')
        choice(name: 'RELEASETYPE', choices: ['user', 'userdebug', 'eng'], description: 'Build release type')
        choice(name: 'INSTALLCLEAN', choices: ['Yes', 'No'], description: 'Run build with make installclean')
        choice(name: 'FULLCLEAN', choices: ['No', 'Yes'], description: 'Run build with make clean (cleans entire out dir)')
        choice(name: 'FSGEN', choices: ['Enable', 'Disable'], description: 'Disable soong_filesystem_creator for certain builds')
        choice(name: 'GMS_VARIANT', choices: ['Tree default', 'Full', 'Core', 'Basic', 'Vanilla'], description: 'Choose GMS variant to apply')
        choice(name: 'RELEASE_BUILD', choices: ['No', 'Yes'], description: 'Release your build directly or not')
        string(name: 'LOCAL_MANIFEST_URL', defaultValue: '', description: 'URL to local_manifest.xml (optional)')
        
        // Hidden parameters for Bot Integration
        string(name: 'BUILD_USER', defaultValue: 'Jenkins', description: 'Username of the trigger (Bot)')
        string(name: 'BUILD_USER_ID', defaultValue: '0', description: 'Telegram ID of the trigger (Bot)')
    }

    environment {
        // Define AOSP source directory centrally
        AOSP_SOURCE_DIR = "$HOME/android/source"

        // Global Variable
        FULL_CLEAN = "${(params.FULLCLEAN == 'Yes') ? 'true' : 'false'}"
        RELEASE_BUILD = "${(params.RELEASE_BUILD == 'Yes') ? 'true' : 'false'}"
        
        // Credentials & Telegram Config
        TELEGRAM_TOKEN = credentials('telegram-token')
        TELEGRAM_CHAT_ID = credentials('telegram-chat-id') 
        TOPIC_BUILDER = credentials('telegram-topic-builder')
        TOPIC_ERROR_LOGS = credentials('telegram-topic-error-logs')
        TOPIC_RELEASE_JSON = credentials('telegram-topic-release-json')

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

    stages {
        stage('Notify Start') {
            steps {
                script {
                    sh "chmod +x ${env.WORKSPACE}/builder/*.py"
                    sh "chmod +x ${env.WORKSPACE}/builder/*.sh"
                    
                    echo "Sending Start Notification..."
                    sh """
                        python3 ${env.WORKSPACE}/builder/reporter.py \
                        --status started \
                        --device "${params.DEVICE}" \
                        --build-type "${params.RELEASETYPE}" \
                        --release-status "${params.RELEASE_BUILD}" \
                        --gms "${params.GMS_VARIANT}" \
                        --fsgen "${params.FSGEN}" \
                        --user "${params.BUILD_USER}" \
                        --chat-id "${TELEGRAM_CHAT_ID}" \
                        --topic-builder "${TOPIC_BUILDER}" \
                        --topic-error-logs "${TOPIC_ERROR_LOGS}" \
                        --topic-release-json "${TOPIC_RELEASE_JSON}" \
                        --token "${TELEGRAM_TOKEN}" \
                        --build-url "${env.BUILD_URL}"
                    """
                }
            }
        }
        stage('Check Quota') {
            steps {
                script {
                    // Only check if triggered by a valid Telegram User ID
                    if (params.BUILD_USER_ID != '0' && params.BUILD_USER_ID != '') {
                        echo "Checking & Updating Quota for User: ${params.BUILD_USER} (${params.BUILD_USER_ID})"
                        sh "python3 ${env.WORKSPACE}/builder/quota_manager.py '${params.BUILD_USER_ID}' '${params.BUILD_USER}'"
                    } else {
                        echo "Build triggered manually/internally. Skipping quota check."
                    }
                }
            }
        }
        stage('Syncing Source') {
            steps {
                script {
                    sh """
                        git config --global user.name "HinohArata"
                        git config --global user.email "161218134+HinohArata@users.noreply.github.com"
                        cd $AOSP_SOURCE_DIR
                        ${env.WORKSPACE}/builder/sync.sh "${params.LOCAL_MANIFEST_URL}"
                    """
                }
            }
        }
        stage('Set GMS Variant') {
            when { expression { params.GMS_VARIANT != 'Tree default' } }
            steps {
                script {
                    sh """
                        echo "GMS Variant is set to '${params.GMS_VARIANT}'. Applying changes..."
                        cd $AOSP_SOURCE_DIR
                        ${env.WORKSPACE}/builder/gms_variant_control.sh "${params.DEVICE}" "${params.GMS_VARIANT}"
                    """
                }
            }
        }
        stage('Modify FSGen') {
            when { expression { params.FSGEN == 'Disable' } }
            steps {
                script {
                    sh """
                        echo "FSGen is disabled. Modifying Android.bp..."
                        cd $AOSP_SOURCE_DIR
                        ${env.WORKSPACE}/builder/fsgen_control.sh modify
                    """
                }
            }
        }

        stage('Building') {
            steps {
                script {
                    sh """
                        cd $AOSP_SOURCE_DIR
                        ${env.WORKSPACE}/builder/build.sh \
                        "${params.DEVICE}" \
                        "${params.RELEASETYPE}" \
                        "${params.INSTALLCLEAN}" \
                        "${params.FULLCLEAN}"
                    """
                }
            }
        }
    }
    
    post {
        always {
            script {
                if (params.FSGEN == 'Disable') {
                    sh """
                        echo "Build finished. Restoring Android.bp..."
                        cd $AOSP_SOURCE_DIR
                        ${env.WORKSPACE}/builder/fsgen_control.sh restore
                    """
                }
            }
        }
        success {
            script {
                echo "Build Success! Reporting..."
                sh """
                    python3 ${env.WORKSPACE}/builder/reporter.py \
                    --status success \
                    --device "${params.DEVICE}" \
                    --build-type "${params.RELEASETYPE}" \
                    --release-status "${params.RELEASE_BUILD}" \
                    --gms "${params.GMS_VARIANT}" \
                    --fsgen "${params.FSGEN}" \
                    --user "${params.BUILD_USER}" \
                    --chat-id "${TELEGRAM_CHAT_ID}" \
                    --topic-builder "${TOPIC_BUILDER}" \
                    --topic-error-logs "${TOPIC_ERROR_LOGS}" \
                    --topic-release-json "${TOPIC_RELEASE_JSON}" \
                    --token "${TELEGRAM_TOKEN}" \
                    --build-url "${env.BUILD_URL}"
                """
            }
        }
        failure {
            script {
                echo "Build Failed! Reporting failure..."
                sh """
                    python3 ${env.WORKSPACE}/builder/reporter.py \
                    --status failure \
                    --device "${params.DEVICE}" \
                    --build-type "${params.RELEASETYPE}" \
                    --release-status "${params.RELEASE_BUILD}" \
                    --gms "${params.GMS_VARIANT}" \
                    --fsgen "${params.FSGEN}" \
                    --user "${params.BUILD_USER}" \
                    --chat-id "${TELEGRAM_CHAT_ID}" \
                    --topic-builder "${TOPIC_BUILDER}" \
                    --topic-error-logs "${TOPIC_ERROR_LOGS}" \
                    --topic-release-json "${TOPIC_RELEASE_JSON}" \
                    --token "${TELEGRAM_TOKEN}" \
                    --build-url "${env.BUILD_URL}"
                """
            }
        }
        aborted {
            script {
                echo "Build Aborted! Reporting..."
                sh """
                    python3 ${env.WORKSPACE}/builder/reporter.py \
                    --status aborted \
                    --device "${params.DEVICE}" \
                    --build-type "${params.RELEASETYPE}" \
                    --release-status "${params.RELEASE_BUILD}" \
                    --gms "${params.GMS_VARIANT}" \
                    --fsgen "${params.FSGEN}" \
                    --user "${params.BUILD_USER}" \
                    --chat-id "${TELEGRAM_CHAT_ID}" \
                    --topic-builder "${TOPIC_BUILDER}" \
                    --topic-error-logs "${TOPIC_ERROR_LOGS}" \
                    --topic-release-json "${TOPIC_RELEASE_JSON}" \
                    --token "${TELEGRAM_TOKEN}" \
                    --build-url "${env.BUILD_URL}"
                """
            }
        }
    }
}


