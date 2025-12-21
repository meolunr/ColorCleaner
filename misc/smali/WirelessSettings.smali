.class public Lcom/meolunr/colorcleaner/CcInjector;
.super Ljava/lang/Object;


# direct methods
.method public constructor <init>()V
    .locals 0

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    return-void
.end method

.method public static showNetmaskAndGateway(Landroid/content/Context;Landroidx/preference/Preference;Landroidx/preference/Preference;Landroidx/preference/Preference;)V
    .locals 19

    move-object/from16 v0, p0

    move-object/from16 v1, p1

    move-object/from16 v2, p2

    move-object/from16 v3, p3

    invoke-virtual {v2}, Landroidx/preference/Preference;->isVisible()Z

    move-result v4

    invoke-virtual {v3}, Landroidx/preference/Preference;->isVisible()Z

    move-result v5

    const/4 v6, 0x1

    if-eqz v4, :cond_0

    if-eqz v5, :cond_0

    invoke-virtual {v2}, Landroidx/preference/Preference;->getSummary()Ljava/lang/CharSequence;

    move-result-object v7

    invoke-virtual {v3}, Landroidx/preference/Preference;->getSummary()Ljava/lang/CharSequence;

    move-result-object v8

    new-instance v9, Ljava/lang/StringBuilder;

    invoke-direct {v9}, Ljava/lang/StringBuilder;-><init>()V

    invoke-static {v7}, Ljava/lang/String;->valueOf(Ljava/lang/Object;)Ljava/lang/String;

    move-result-object v10

    invoke-virtual {v9, v10}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v9

    const/16 v10, 0xa

    invoke-virtual {v9, v10}, Ljava/lang/StringBuilder;->append(C)Ljava/lang/StringBuilder;

    move-result-object v9

    invoke-virtual {v9, v8}, Ljava/lang/StringBuilder;->append(Ljava/lang/Object;)Ljava/lang/StringBuilder;

    move-result-object v9

    invoke-virtual {v9}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v9

    invoke-virtual {v1, v6}, Landroidx/preference/Preference;->setVisible(Z)V

    invoke-virtual {v1, v9}, Landroidx/preference/Preference;->setSummary(Ljava/lang/CharSequence;)V

    :cond_0
    const-class v7, Landroid/net/ConnectivityManager;

    invoke-virtual {v0, v7}, Landroid/content/Context;->getSystemService(Ljava/lang/Class;)Ljava/lang/Object;

    move-result-object v7

    check-cast v7, Landroid/net/ConnectivityManager;

    const-class v8, Landroid/net/wifi/WifiManager;

    invoke-virtual {v0, v8}, Landroid/content/Context;->getSystemService(Ljava/lang/Class;)Ljava/lang/Object;

    move-result-object v8

    check-cast v8, Landroid/net/wifi/WifiManager;

    invoke-virtual {v8}, Landroid/net/wifi/WifiManager;->getCurrentNetwork()Landroid/net/Network;

    move-result-object v9

    invoke-virtual {v7, v9}, Landroid/net/ConnectivityManager;->getLinkProperties(Landroid/net/Network;)Landroid/net/LinkProperties;

    move-result-object v9

    if-eqz v4, :cond_3

    invoke-virtual {v9}, Landroid/net/LinkProperties;->getLinkAddresses()Ljava/util/List;

    move-result-object v12

    invoke-interface {v12}, Ljava/util/List;->iterator()Ljava/util/Iterator;

    move-result-object v12

    :goto_0
    invoke-interface {v12}, Ljava/util/Iterator;->hasNext()Z

    move-result v13

    if-eqz v13, :cond_2

    invoke-interface {v12}, Ljava/util/Iterator;->next()Ljava/lang/Object;

    move-result-object v13

    check-cast v13, Landroid/net/LinkAddress;

    invoke-virtual {v13}, Landroid/net/LinkAddress;->getAddress()Ljava/net/InetAddress;

    move-result-object v14

    instance-of v14, v14, Ljava/net/Inet4Address;

    if-eqz v14, :cond_1

    invoke-virtual {v13}, Landroid/net/LinkAddress;->getPrefixLength()I

    move-result v12

    rsub-int/lit8 v12, v12, 0x20

    const/4 v14, -0x1

    shl-int v12, v14, v12

    shr-int/lit8 v14, v12, 0x18

    and-int/lit16 v14, v14, 0xff

    shr-int/lit8 v15, v12, 0x10

    and-int/lit16 v15, v15, 0xff

    const/16 v16, 0x2

    shr-int/lit8 v10, v12, 0x8

    and-int/lit16 v10, v10, 0xff

    const/16 v17, 0x0

    and-int/lit16 v11, v12, 0xff

    filled-new-array {v14, v15, v10, v11}, [I

    move-result-object v10

    invoke-virtual {v2, v6}, Landroidx/preference/Preference;->setVisible(Z)V

    const-string v11, "\u5b50\u7f51\u63a9\u7801"

    invoke-virtual {v2, v11}, Landroidx/preference/Preference;->setTitle(Ljava/lang/CharSequence;)V

    aget v11, v10, v17

    invoke-static {v11}, Ljava/lang/Integer;->valueOf(I)Ljava/lang/Integer;

    move-result-object v11

    aget v14, v10, v6

    invoke-static {v14}, Ljava/lang/Integer;->valueOf(I)Ljava/lang/Integer;

    move-result-object v14

    aget v15, v10, v16

    invoke-static {v15}, Ljava/lang/Integer;->valueOf(I)Ljava/lang/Integer;

    move-result-object v15

    const/16 v18, 0x3

    aget v18, v10, v18

    invoke-static/range {v18 .. v18}, Ljava/lang/Integer;->valueOf(I)Ljava/lang/Integer;

    move-result-object v6

    filled-new-array {v11, v14, v15, v6}, [Ljava/lang/Object;

    move-result-object v6

    const-string v11, "%d.%d.%d.%d"

    invoke-static {v11, v6}, Ljava/lang/String;->format(Ljava/lang/String;[Ljava/lang/Object;)Ljava/lang/String;

    move-result-object v6

    invoke-virtual {v2, v6}, Landroidx/preference/Preference;->setSummary(Ljava/lang/CharSequence;)V

    goto :goto_1

    :cond_1
    const/16 v16, 0x2

    const/16 v17, 0x0

    const/4 v6, 0x1

    goto :goto_0

    :cond_2
    const/16 v16, 0x2

    const/16 v17, 0x0

    :goto_1
    goto :goto_2

    :cond_3
    const/16 v16, 0x2

    const/16 v17, 0x0

    move/from16 v6, v17

    invoke-virtual {v2, v6}, Landroidx/preference/Preference;->setVisible(Z)V

    :goto_2
    new-instance v6, Ljava/util/ArrayList;

    invoke-direct {v6}, Ljava/util/ArrayList;-><init>()V

    invoke-virtual {v9}, Landroid/net/LinkProperties;->getRoutes()Ljava/util/List;

    move-result-object v10

    invoke-interface {v10}, Ljava/util/List;->iterator()Ljava/util/Iterator;

    move-result-object v10

    :goto_3
    invoke-interface {v10}, Ljava/util/Iterator;->hasNext()Z

    move-result v11

    if-eqz v11, :cond_7

    invoke-interface {v10}, Ljava/util/Iterator;->next()Ljava/lang/Object;

    move-result-object v11

    check-cast v11, Landroid/net/RouteInfo;

    invoke-virtual {v11}, Landroid/net/RouteInfo;->isDefaultRoute()Z

    move-result v12

    if-nez v12, :cond_4

    goto :goto_3

    :cond_4
    invoke-virtual {v11}, Landroid/net/RouteInfo;->getGateway()Ljava/net/InetAddress;

    move-result-object v12

    instance-of v13, v12, Ljava/net/Inet4Address;

    if-eqz v13, :cond_5

    invoke-virtual {v12}, Ljava/net/InetAddress;->getHostAddress()Ljava/lang/String;

    move-result-object v13

    const/4 v14, 0x0

    invoke-virtual {v6, v14, v13}, Ljava/util/ArrayList;->add(ILjava/lang/Object;)V

    goto :goto_4

    :cond_5
    invoke-virtual {v12}, Ljava/net/InetAddress;->getHostAddress()Ljava/lang/String;

    move-result-object v13

    invoke-virtual {v6, v13}, Ljava/util/ArrayList;->add(Ljava/lang/Object;)Z

    :goto_4
    invoke-virtual {v6}, Ljava/util/ArrayList;->size()I

    move-result v13

    move/from16 v14, v16

    if-ne v13, v14, :cond_6

    goto :goto_5

    :cond_6
    move/from16 v16, v14

    goto :goto_3

    :cond_7
    :goto_5
    invoke-virtual {v6}, Ljava/util/ArrayList;->isEmpty()Z

    move-result v10

    if-nez v10, :cond_8

    const/4 v10, 0x1

    invoke-virtual {v3, v10}, Landroidx/preference/Preference;->setVisible(Z)V

    const-string v10, "\u7f51\u5173"

    invoke-virtual {v3, v10}, Landroidx/preference/Preference;->setTitle(Ljava/lang/CharSequence;)V

    const-string v10, "\n"

    invoke-static {v10, v6}, Ljava/lang/String;->join(Ljava/lang/CharSequence;Ljava/lang/Iterable;)Ljava/lang/String;

    move-result-object v10

    invoke-virtual {v3, v10}, Landroidx/preference/Preference;->setSummary(Ljava/lang/CharSequence;)V

    goto :goto_6

    :cond_8
    const/4 v14, 0x0

    invoke-virtual {v3, v14}, Landroidx/preference/Preference;->setVisible(Z)V

    :goto_6
    return-void
.end method
