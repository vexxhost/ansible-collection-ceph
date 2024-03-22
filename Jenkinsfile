pipeline {
  agent none

  options {
    disableConcurrentBuilds(abortPrevious: true);
  }

  stages {
    stage('integration') {
      matrix {
        axes {
          axis {
            name 'SCENARIO'
            values 'ha'
            //values 'ha', 'aio'
            // TODO reduce resources per case so we can run them all
          }
          axis {
            name 'VERSION'
            values '16.2.14', '17.2.7', '18.2.1'
          }
          axis {
            name 'DISTRO'
            values 'ubuntu2004', 'ubuntu2204'
          }
          axis {
            name 'TESTCASE'
            values 'general', 'adopt'
          }
        }

        agent {
          label 'jammy-2c-8g'
        }

        environment {
          MOLECULE_CEPH_FSID=UUID.randomUUID().toString()
          MOLECULE_CEPH_VERSION="${VERSION}"
          MOLECULE_DISTRO="${DISTRO}"
          LAST_VERSION="18.2.1"
          LEGACY_BRANCH="d9bef03f7166d263bfa9059b869de0d7e867015e" //"v2.2.0"
          BUILD_RESULT_ON_FAILURE = "${TESTCASE == 'adopt' ? 'SUCCESS' : 'FAILURE'}"
          STAGE_RESULT_ON_FAILURE = "${TESTCASE == 'adopt' ? 'UNSTABLE' : 'FAILURE'}"
        }

        stages {
          // Install, verify
          stage('ubuntu2204') {
            when { expression { env.DISTRO == "ubuntu2204" && env.VERSION == env.LAST_VERSION && env.TESTCASE == 'general' } }
            steps {

              sh 'sudo apt-get purge -y snapd'
              sh 'sudo apt-get install -y git python3-pip docker.io'
              sh 'sudo pip install -r requirements.txt'
              sh "sudo molecule test -s ${SCENARIO}"
            }
          }
          stage('ubuntu2004') {
            when { expression { env.DISTRO == "ubuntu2004" && env.TESTCASE == 'general' } }
            steps {

              sh 'sudo apt-get purge -y snapd'
              sh 'sudo apt-get install -y git python3-pip docker.io'
              sh 'sudo pip install -r requirements.txt'
              sh "sudo molecule test -s ${SCENARIO}"
            }
          }
          // upgrade and verify
          stage('upgrade') {
            when { expression { env.DISTRO == "ubuntu2004" && env.VERSION != env.LAST_VERSION && env.SCENARIO == "ha" && env.TESTCASE == 'general' } }
            steps {
              sh "MOLECULE_CEPH_VERSION=${LAST_VERSION} && sudo molecule converge -s ${SCENARIO}"
              sh "MOLECULE_CEPH_VERSION=${LAST_VERSION} && sudo molecule verify -s ${SCENARIO}"
            }
          }
          // adopt from legacy environment to cephadm env.
          stage('adopt') {
            when { expression { env.DISTRO == "ubuntu2004" && env.VERSION != env.LAST_VERSION && env.SCENARIO == "ha" && env.TESTCASE == 'adopt' } }
            agent {
              label 'jammy-16c-32g'
            }
            steps {
              catchError(buildResult: "${BUILD_RESULT_ON_FAILURE}", stageResult: "${STAGE_RESULT_ON_FAILURE}") {
                  sh "git checkout -B ${GIT_BRANCH}"
                  sh 'sudo apt-get purge -y snapd'
                  sh 'sudo apt-get install -y git python3-pip docker.io'
                  sh "git checkout ${LEGACY_BRANCH}"
                  sh 'sudo pip install -r requirements.txt'
                  sh "sudo molecule converge -s ${SCENARIO}"
                  sh "sudo molecule verify -s ${SCENARIO}"
                  sh "git checkout ${GIT_BRANCH}"
                  sh 'sudo pip install -r requirements.txt'
                  sh "sudo molecule converge -s ${SCENARIO}"
                  sh "sudo molecule verify -s ${SCENARIO}"
              }

            }
          }
        }
      }
    }
  }
}
