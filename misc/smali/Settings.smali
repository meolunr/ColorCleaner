.class public Lcom/meolunr/colorcleaner/CcInjector;
.super Ljava/lang/Object;


# direct methods
.method public constructor <init>()V
    .locals 0

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    return-void
.end method

.method public static setPackageAndVersion(Landroid/widget/TextView;Landroid/content/pm/PackageInfo;)V
    .locals 6

    new-instance v0, Landroid/text/SpannableString;

    iget-object v1, p1, Landroid/content/pm/PackageInfo;->packageName:Ljava/lang/String;

    invoke-direct {v0, v1}, Landroid/text/SpannableString;-><init>(Ljava/lang/CharSequence;)V

    invoke-virtual {p0}, Landroid/widget/TextView;->getTextSize()F

    move-result v1

    const/high16 v2, 0x40c00000

    add-float/2addr v1, v2

    float-to-int v1, v1

    new-instance v2, Landroid/text/style/AbsoluteSizeSpan;

    invoke-direct {v2, v1}, Landroid/text/style/AbsoluteSizeSpan;-><init>(I)V

    iget-object v3, p1, Landroid/content/pm/PackageInfo;->packageName:Ljava/lang/String;

    invoke-virtual {v3}, Ljava/lang/String;->length()I

    move-result v3

    const/16 v4, 0x21

    const/4 v5, 0x0

    invoke-virtual {v0, v2, v5, v3, v4}, Landroid/text/SpannableString;->setSpan(Ljava/lang/Object;III)V

    const/4 v3, 0x6

    new-array v3, v3, [Ljava/lang/CharSequence;

    aput-object v0, v3, v5

    const/4 v4, 0x1

    const-string v5, "\n\u7248\u672c "

    aput-object v5, v3, v4

    const/4 v4, 0x2

    iget-object v5, p1, Landroid/content/pm/PackageInfo;->versionName:Ljava/lang/String;

    aput-object v5, v3, v4

    const/4 v4, 0x3

    const-string v5, " ("

    aput-object v5, v3, v4

    invoke-virtual {p1}, Landroid/content/pm/PackageInfo;->getLongVersionCode()J

    move-result-wide v4

    invoke-static {v4, v5}, Ljava/lang/String;->valueOf(J)Ljava/lang/String;

    move-result-object v4

    const/4 v5, 0x4

    aput-object v4, v3, v5

    const/4 v4, 0x5

    const-string v5, ")"

    aput-object v5, v3, v4

    invoke-static {v3}, Landroid/text/TextUtils;->concat([Ljava/lang/CharSequence;)Ljava/lang/CharSequence;

    move-result-object v3

    invoke-virtual {p0, v3}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V

    return-void
.end method
