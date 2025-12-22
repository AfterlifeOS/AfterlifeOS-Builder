pipeline {
    agent { label 'AfterlifeOS-Controller' }
    parameters {
        string(name: 'DEVICE', defaultValue: 'walleye', description: 'Device name (e.g., walleye)')
        choice(name: 'RELEASETYPE', choices: ['user', 'userdebug', 'eng'], description: 'Build release type')
        choice(name: 'INSTALLCLEAN', choices: ['Yes', 'No'], description: 'Run build with make installclean')
        choice(name: 'FULLCLEAN', choices: ['No', 'Yes'], description: 'Run build with make clean (cleans entire out dir)')
        choice(name: 'FSGEN', choices: ['Enable', 'Disable'], description: 'Disable soong_filesystem_creator for certain builds')
        choice(name: 'GMS_VARIANT', choices: ['Tree default', 'Full', 'Core', 'Basic', 'Vanilla'], description: 'Choose GMS variant to apply')
        choice(name: 'RELEASE_BUILD', choices: ['No', 'Yes'], description: 'Release your build directly or not')
        string(name: 'LOCAL_MANIFEST_URL', defaultValue: '', description: 'URL to local_manifest.xml (optional)')
        string(name: 'BUILD_USER', defaultValue: 'Jenkins', description: 'Username of the trigger (Bot)')
        string(name: 'BUILD_USER_ID', defaultValue: '0', description: 'Telegram ID of the trigger (Bot)')
    }

    stages {
        stage('Provision Device Job') {
            steps {
                script {
                    // Create folder first
                    jobDsl scriptText: "folder('AfterlifeOS') { description('Device Builds for AfterlifeOS') }"

                    def jobName = "AfterlifeOS/${params.DEVICE}"

                    jobDsl scriptText: """
                        pipelineJob('${jobName}') {
                            description("Build Job Automation for ${params.DEVICE}")
                            logRotator {
                                numToKeep(10)
                                artifactNumToKeep(10)
                            }

                            parameters {
                                stringParam('DEVICE', '${params.DEVICE}', 'Device Codename')
                                stringParam('RELEASETYPE', 'userdebug', 'Build Type')
                                stringParam('INSTALLCLEAN', 'Yes', 'Installclean?')
                                stringParam('FULLCLEAN', 'No', 'Fullclean?')
                                stringParam('FSGEN', 'Enable', 'FSGen Status')
                                stringParam('GMS_VARIANT', 'Tree default', 'GMS Variant')
                                stringParam('RELEASE_BUILD', 'No', 'Release Status')
                                stringParam('LOCAL_MANIFEST_URL', '', 'Local Manifest')
                                stringParam('BUILD_USER', 'Jenkins', 'User Trigger')
                                stringParam('BUILD_USER_ID', '0', 'User ID Trigger')
                            }

                            definition {
                                cpsScm {
                                    scm {
                                        git {
                                            remote { 
                                                url('${env.GIT_URL}') 
                                            }
                                            branch('new')
                                        }
                                    }
                                    scriptPath('pipelines/device.jenkinsfile')
                                }
                            }
                        }
                    """
                }
            }
        }

        stage('Trigger Build') {
            steps {
                script {
                    def jobName = "AfterlifeOS/${params.DEVICE}"
                    echo "Triggering downstream build: ${jobName}"
                    build job: jobName, parameters: [
                        string(name: 'DEVICE', value: params.DEVICE),
                        string(name: 'RELEASETYPE', value: params.RELEASETYPE),
                        string(name: 'INSTALLCLEAN', value: params.INSTALLCLEAN),
                        string(name: 'FULLCLEAN', value: params.FULLCLEAN),
                        string(name: 'FSGEN', value: params.FSGEN),
                        string(name: 'GMS_VARIANT', value: params.GMS_VARIANT),
                        string(name: 'RELEASE_BUILD', value: params.RELEASE_BUILD),
                        string(name: 'LOCAL_MANIFEST_URL', value: params.LOCAL_MANIFEST_URL),
                        string(name: 'BUILD_USER', value: params.BUILD_USER),
                        string(name: 'BUILD_USER_ID', value: params.BUILD_USER_ID)
                    ], wait: false
                }
            }
        }
    }
}