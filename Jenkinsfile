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
            values 'ha', 'aio'
          }
          axis {
            name 'VERSION'
            values '16.2.14', '17.2.7', '18.2.1'
          }
          axis {
            name 'DISTRO'
            values 'ubuntu2004', 'ubuntu2204'
          }
        }

        agent {
          label 'jammy-16c-64g'
        }

        environment {
          MOLECULE_CEPH_FSID=UUID.randomUUID().toString()
          MOLECULE_CEPH_VERSION="${VERSION}"
          MOLECULE_DISTRO="${DISTRO}"
          LAST_VERSION="18.2.1"
          LEGACY_BRANCH="v2.2.0"
        }

        stages {
          stage('ubuntu2204') {
            when { expression { env.DISTRO == "ubuntu2204" && env.VERSION == env.LAST_VERSION } }
            steps {

              // Install dependencies
              sh 'sudo apt-get purge -y snapd'
              sh 'sudo apt-get install -y git python3-pip docker.io'
              sh 'sudo pip install -r requirements.txt'
              sh "sudo molecule test -s ${SCENARIO}"
            }
          }
          stage('ubuntu2004') {
            when { expression { env.DISTRO == "ubuntu2004" } }
            steps {

              // Install dependencies
              sh 'sudo apt-get purge -y snapd'
              sh 'sudo apt-get install -y git python3-pip docker.io'
              sh 'sudo pip install -r requirements.txt'
              sh "sudo molecule test -s ${SCENARIO}"
            }
          }
          stage('adopt') {
            when { expression { env.DISTRO == "ubuntu2004" && env.VERSION != env.LAST_VERSION && env.SCENARIO == "ha" } }
            steps {

              // Install dependencies
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
          stage('upgrade') {
            when { expression { env.DISTRO == "ubuntu2004" && env.VERSION != env.LAST_VERSION && env.SCENARIO == "ha" } }
            steps {

              // Install dependencies
              sh 'sudo apt-get purge -y snapd'
              sh 'sudo apt-get install -y git python3-pip docker.io'
              sh "git checkout ${LEGACY_BRANCH}"
              sh 'sudo pip install -r requirements.txt'
              sh "sudo molecule converge -s ${SCENARIO}"
              sh "sudo molecule verify -s ${SCENARIO}"
              sh "git checkout ${GIT_BRANCH}"
              sh 'sudo pip install -r requirements.txt'
              sh "MOLECULE_CEPH_VERSION=${LAST_VERSION} && sudo molecule converge -s ${SCENARIO}"
              sh "MOLECULE_CEPH_VERSION=${LAST_VERSION} && sudo molecule verify -s ${SCENARIO}"
            }
          }

        }
      }
    }
  }
}
