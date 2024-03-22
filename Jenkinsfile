def lastCephVersion = "18.2.1"
def legacyBranch="d9bef03f7166d263bfa9059b869de0d7e867015e" //"v2.2.0"
def fsid = "${UUID.randomUUID().toString()}"
def operatingSystems = ['ubuntu2004', 'ubuntu2204']
def previousCephVersions = ['16.2.14', '17.2.7']
def scenarios = ['ha', 'aio']
def testcase = ['general', 'adopt']

def integrationJobs = [:]
// Test for all non-last version install and upgrade to latest
previousCephVersions.each { cephVersion ->
    scenarios.each { scenario ->
        integrationJobs["ubuntu2004-${cephVersion}-${scenario}-with-upgrade"] = {
            node('jammy-2c-8g') {
                checkout scm
                sh 'sudo apt-get purge -y snapd'
                sh 'sudo apt-get install -y git python3-pip docker.io'
                sh 'sudo pip install -r requirements.txt'
                withEnv([
                    "MOLECULE_CEPH_FSID=${fsid}",
                    "MOLECULE_CEPH_VERSION=${cephVersion}",
                    "MOLECULE_DISTRO=ubuntu2004"
                ]) {
                    sh "sudo molecule test -s ${scenario}"
                }
                withEnv([
                    "MOLECULE_CEPH_FSID=${fsid}",
                    "MOLECULE_CEPH_VERSION=${lastCephVersion}",
                    "MOLECULE_DISTRO=ubuntu2004"
                ]) {
                    sh "sudo molecule converge -s ${scenario}"
                    sh "sudo molecule verify -s ${scenario}"
                }
            }
        }
    }
}
// Test latest version
operatingSystems.each { operatingSystem ->
    scenarios.each { scenario ->
        integrationJobs["${operatingSystem}-${lastCephVersion}-${scenario}-latest"] = {
            node('jammy-2c-8g') {
                checkout scm
                sh 'sudo apt-get purge -y snapd'
                sh 'sudo apt-get install -y git python3-pip docker.io'
                sh 'sudo pip install -r requirements.txt'
                withEnv([
                    "MOLECULE_CEPH_FSID=${fsid}",
                    "MOLECULE_CEPH_VERSION=${lastCephVersion}",
                    "MOLECULE_DISTRO=${operatingSystem}"
                ]) {
                    sh "sudo molecule test -s ${scenario}"
                }
            }
        }
    }
}

// Test for previous versions with adopt
previousCephVersions.each { cephVersion ->
    integrationJobs["ubuntu2004-${cephVersion}-ha-adopt-legacy"] = {
        node('jammy-16c-64g') {
            checkout scm
            sh "git checkout ${legacyBranch}"
            sh 'sudo apt-get purge -y snapd'
            sh 'sudo apt-get install -y git python3-pip docker.io'
            sh 'sudo pip install -r requirements.txt'
            withEnv([
                "MOLECULE_CEPH_FSID=${fsid}",
                "MOLECULE_CEPH_VERSION=${cephVersion}",
                "MOLECULE_DISTRO=ubuntu2004"
            ]) {
                sh "sudo molecule converge -s ha"
                sh "sudo molecule verify -s ha"
                checkout scm
                sh 'sudo pip install -r requirements.txt'
                sh "sudo molecule converge -s ha"
                sh "sudo molecule verify -s ha"
            }
        }
    }
}

parallel integrationJobs
