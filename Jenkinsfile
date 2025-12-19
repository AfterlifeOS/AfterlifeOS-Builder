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
        DEVICE = "${params.DEVICE}"
        RELEASETYPE = "${params.RELEASETYPE}"
        INSTALLCLEAN = "${params.INSTALLCLEAN}"
        GMS_VARIANT = "${params.GMS_VARIANT}"
        FSGEN = "${params.FSGEN}"
        BUILD_USER = "${params.BUILD_USER}"
        BUILD_USER_ID = "${params.BUILD_USER_ID}"
        FULLCLEAN = "${(params.FULLCLEAN == 'Yes') ? 'true' : 'false'}"
        RELEASE_BUILD = "${(params.RELEASE_BUILD == 'Yes') ? 'true' : 'false'}"
        LOCAL_MANIFEST = "${params.LOCAL_MANIFEST_URL}"
        
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
                    
                    // Clean up old logs to prevent false reporting
                    sh "rm -f ${env.WORKSPACE}/build.log ${env.WORKSPACE}/sync.log ${env.WORKSPACE}/.quota_exceeded ${AOSP_SOURCE_DIR}/out/error.log"
                    
                    echo "Sending Start Notification..."
                    sh '''
                        python3 ${WORKSPACE}/builder/reporter.py \
                        --status started \
                        --device "${DEVICE}" \
                        --build-type "${RELEASETYPE}" \
                        --release-status "${RELEASE_BUILD}" \
                        --gms "${GMS_VARIANT}" \
                        --fsgen "${FSGEN}" \
                        --install-clean "${INSTALLCLEAN}" \
                        --full-clean "${FULLCLEAN}" \
                        --user "${BUILD_USER}" \
                        --chat-id "${TELEGRAM_CHAT_ID}" \
                        --topic-builder "${TOPIC_BUILDER}" \
                        --topic-error-logs "${TOPIC_ERROR_LOGS}" \
                        --topic-release-json "${TOPIC_RELEASE_JSON}" \
                        --token "${TELEGRAM_TOKEN}" \
                        --build-url "${BUILD_URL}" \
                        --source-dir "${AOSP_SOURCE_DIR}"
                    '''
                }
            }
        }
        stage('Check Quota') {
            steps {
                script {
                    // Only check if triggered by a valid Telegram User ID
                    if (BUILD_USER_ID != '0' && BUILD_USER_ID != '') {
                        echo "Checking & Updating Quota for User: ${BUILD_USER} (${BUILD_USER_ID})"
                        sh "python3 ${env.WORKSPACE}/builder/quota_manager.py '${BUILD_USER_ID}' '${BUILD_USER}' '${FULLCLEAN}'"
                    } else {
                        echo "Build triggered manually/internally. Skipping quota check."
                    }
                }
            }
        }
        stage('Syncing Source') {
            steps {
                script {
                    sh '''
                        git config --global user.name "HinohArata"
                        git config --global user.email "161218134+HinohArata@users.noreply.github.com"
                        cd $AOSP_SOURCE_DIR
                        ${WORKSPACE}/builder/sync.sh "${LOCAL_MANIFEST}"
                    '''
                }
            }
        }
        stage('Set GMS Variant') {
            when { expression { GMS_VARIANT != 'Tree default' } }
            steps {
                script {
                    sh '''
                        echo "GMS Variant is set to '${GMS_VARIANT}'. Applying changes..."
                        cd $AOSP_SOURCE_DIR
                        ${WORKSPACE}/builder/gms_variant_control.sh apply "${DEVICE}" "${GMS_VARIANT}"
                    '''
                }
            }
        }
        stage('Modify FSGen') {
            when { expression { FSGEN == 'Disable' } }
            steps {
                script {
                    sh '''
                        echo "FSGen is disabled. Modifying Android.bp..."
                        cd $AOSP_SOURCE_DIR
                        ${WORKSPACE}/builder/fsgen_control.sh modify
                    '''
                }
            }
        }

        stage('Building') {
            steps {
                script {
                    sh '''
                        cd $AOSP_SOURCE_DIR
                        ${WORKSPACE}/builder/build.sh \
                        "${DEVICE}" \
                        "${RELEASETYPE}" \
                        "${INSTALLCLEAN}" \
                        "${FULLCLEAN}"
                    '''
                }
            }
        }
    }
    
    post {
        always {
            script {
                // Restore FSGen if needed
                if (FSGEN == 'Disable') {
                    sh '''
                        echo "Restoring Android.bp..."
                        cd $AOSP_SOURCE_DIR
                        ${WORKSPACE}/builder/fsgen_control.sh restore
                    '''
                }
                
                // Restore GMS Variant if needed (Check if GMS was modified)
                if (GMS_VARIANT != 'Tree default') {
                     sh '''
                        echo "Restoring GMS Variant (Makefile)..."
                        cd $AOSP_SOURCE_DIR
                        ${WORKSPACE}/builder/gms_variant_control.sh restore "${DEVICE}" "ignored"
                     '''
                }
            }
        }
        success {
            script {
                echo "Build Success! Reporting..."
                sendReport('success')
            }
        }
        failure {
            script {
                if (fileExists("${env.WORKSPACE}/.quota_exceeded")) {
                    echo "Quota exceeded. Custom notification already sent. Skipping generic failure report."
                } else {
                    echo "Build Failed! Reporting failure..."
                    sendReport('failure')
                }
            }
        }
        aborted {
            script {
                echo "Build Aborted! Reporting..."
                sendReport('aborted')
            }
        }
    }
}

/* ---------- Helper ---------- */
def sendReport(String buildStatus) {
    withEnv(["BUILD_STATUS_NOTIFICATION=${buildStatus}"]) {
        sh '''
            python3 ${WORKSPACE}/builder/reporter.py \
            --status "${BUILD_STATUS_NOTIFICATION}" \
            --device "${DEVICE}" \
            --build-type "${RELEASETYPE}" \
            --release-status "${RELEASE_BUILD}" \
            --gms "${GMS_VARIANT}" \
            --fsgen "${FSGEN}" \
            --install-clean "${INSTALLCLEAN}" \
            --full-clean "${FULLCLEAN}" \
            --user "${BUILD_USER}" \
            --chat-id "${TELEGRAM_CHAT_ID}" \
            --topic-builder "${TOPIC_BUILDER}" \
            --topic-error-logs "${TOPIC_ERROR_LOGS}" \
            --topic-release-json "${TOPIC_RELEASE_JSON}" \
            --token "${TELEGRAM_TOKEN}" \
            --build-url "${BUILD_URL}" \
            --source-dir "${AOSP_SOURCE_DIR}"
        '''
    }
}
