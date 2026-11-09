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
        versionCode = 11600
        versionName = "1.16.0"
    }
}
