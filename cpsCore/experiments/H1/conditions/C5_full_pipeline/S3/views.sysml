package Views {
    import ComponentModel_S3::*;
    import CPScoreInteractionModels_S3::*;

    view s3structure : GeneralView {
        expose ComponentModel_S3::s3System;
    }

    view s3connections : InterconnectionView {
        expose ComponentModel_S3::s3System;
    }

    view s3Flow : SequenceView {
        expose CPScoreInteractionModels_S3::S3Scenario;
    }
}
