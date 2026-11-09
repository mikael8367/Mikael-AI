plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}
android {
    namespace = "com.mikael.ai"
    compileSdk = 35
    defaultConfig {
        applicationId = "com.mikael.ai"
        minSdk = 26
        targetSdk = 35
        versionCode = 11601
        versionName = "1.16.1"
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}
