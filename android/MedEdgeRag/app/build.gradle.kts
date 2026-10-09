plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.mededge.rag"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.mededge.rag"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
    }

    flavorDimensions += "distribution"
    productFlavors {
        create("offline") {
            dimension = "distribution"
            buildConfigField("boolean", "MODEL_BOOTSTRAP_ENABLED", "false")
            buildConfigField("String", "MODEL_DOWNLOAD_URL", "\"\"")
            buildConfigField("String", "MODEL_SHA256", "\"\"")
        }
        create("bootstrap") {
            dimension = "distribution"
            versionNameSuffix = "-bootstrap"
            buildConfigField("boolean", "MODEL_BOOTSTRAP_ENABLED", "true")
            buildConfigField(
                "String",
                "MODEL_DOWNLOAD_URL",
                "\"https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm/resolve/b4f4f4df93418ddb4aa7da8bf33b584602a5b9f8/gemma-4-E2B-it.litertlm\"",
            )
            buildConfigField(
                "String",
                "MODEL_SHA256",
                "\"181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c\"",
            )
        }
    }

    buildFeatures {
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

kotlin {
    jvmToolchain(17)
}

dependencies {
    implementation("com.google.ai.edge.litertlm:litertlm-android:0.11.0")
}
