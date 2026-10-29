# Farbschemata für E-Mails

Unter E-Mail-Einstellungen → Farbschema der E-Mails stehen Blau (bisheriger Standard), Grau / Schwarzweiß und Regenbogen zur Verfügung. Die Auswahl gilt zentral für Veranstaltungs-, Raumbuchungs- und Kontomails sowie SMTP, Servervorgaben und Microsoft Graph. Sie ist unabhängig von der Aktivierung eigener Versanddaten. Eine Änderung wird durch Speichern übernommen.

Grau / Schwarzweiß verwendet ausschließlich Grautöne. Regenbogen ergänzt eine sechsteilige Farbleiste aus festen Tabellenzellen mit Vollfarben, damit keine Unterstützung von CSS-Verläufen erforderlich ist. Dunkler Text auf weißem Grund, verständliche Linktexte und der automatische Footer bleiben erhalten. Die Palette wird ausschließlich auf feste Gestaltungselemente angewendet; Texte und URLs werden niemals durch Farbersetzung verändert.

Die Einstellungsseite zeigt alle drei Schemata beim Umschalten ohne Versand. HTML-Vorschauen der E-Mail-Vorlagen verwenden denselben Renderer und das gespeicherte Schema. Die Textversion bleibt zusätzlich aufklappbar. Die Vorschauen laufen in Iframes ohne Script-, Formular- oder Top-Navigationsberechtigung.

Bereits wartende Mailaufträge werden erst beim Versand in HTML umgewandelt und verwenden dann das gewählte Schema; ihr Inhalt bleibt gleich. Textversion, Absender, Empfänger, Berechtigungen und Zustelllogik ändern sich nicht.

Migration map.0018 ergänzt das Schema mit Standard Blau. Keine Änderung an Entra/Exchange erforderlich. Die Darstellung wurde im Browser geprüft; einzelne Mailprogramme können zusätzliche eigene Darstellungsanpassungen anwenden. Eine echte Testmail an eure verwendeten Mailprogramme empfiehlt sich nach dem Update.
