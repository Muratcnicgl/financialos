' FinancialOS — pencere AÇMADAN komut çalıştırıcı (BUG #303)
'
' NEDEN VAR: Görev Zamanlayıcı bir görevi kullanıcının OTURUMUNDA koştururken
' powershell.exe/python.exe için bir konsol penceresi yaratır. `-WindowStyle Hidden`
' bunu ENGELLEMEZ — pencere zaten açıldıktan SONRA gizlenir, yani ekranda bir an
' siyah kutu çakar. Sağlık kontrolü 10 dakikada bir koştuğu için bu, çalışan
' kullanıcının önünde günde ~100 kez yanıp sönen bir pencere demekti.
'
' Çözüm: görevi wscript ile başlat, wscript de asıl komutu pencere modu 0 (gizli)
' ile çalıştırsın. Konsol penceresi HİÇ yaratılmaz.
'
' Çıkış kodu KORUNUR (bWaitOnReturn = True): görev zamanlayıcıdaki "sonuc" sütunu
' anlamını yitirmesin ve MultipleInstances=IgnoreNew koruması çalışmaya devam etsin.
' (Beklemeden dönseydik her koşum anında "başarıyla bitti" görünürdü — ölçen sistemin
' yalan söylemesi, hiç ölçmemekten kötüdür.)
'
' Kullanım:
'   wscript.exe //B //Nologo gizli_calistir.vbs <program> [arg1] [arg2] ...

Option Explicit

Dim kabuk, komut, i, kod, parca

If WScript.Arguments.Count = 0 Then
    WScript.Quit 2
End If

Set kabuk = CreateObject("WScript.Shell")

' Tırnak YALNIZ boşluk içeren argümana konur. Her argümanı koşulsuz tırnaklamak,
' `cmd.exe "/c"` gibi anahtar sözcükleri bozuyordu (ilk yazımda `exit 7` denemesi 7
' yerine 1 döndürdü — yani sarmalayıcı, sardığı komutun sonucunu değiştiriyordu).
komut = ""
For i = 0 To WScript.Arguments.Count - 1
    parca = WScript.Arguments(i)
    If InStr(parca, " ") > 0 Then parca = """" & parca & """"
    If i > 0 Then komut = komut & " "
    komut = komut & parca
Next

kod = kabuk.Run(komut, 0, True)
WScript.Quit kod
