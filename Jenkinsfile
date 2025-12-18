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
        string(name: 'LOCAL_MANIFEST_URL', defaultValue: '', description: 'URL to local_manifest.xml (optional)')
    }

    environment {
        // Define AOSP source directory centrally
        AOSP_SOURCE_DIR = "$HOME/android/source"
        FULL_CLEAN = "${(params.FULLCLEAN == 'Yes') ? 'true' : 'false'}"
        
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
        stage('Syncing Source') {
            steps {
                script {
                    sh """
                        chmod -R +x ${env.WORKSPACE}/builder/
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
        stage('Uploading Build') {
            steps {
                script {
                    sh """
                        cd $AOSP_SOURCE_DIR
                        ${env.WORKSPACE}/builder/upload.sh "${params.DEVICE}"
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
    }
}
