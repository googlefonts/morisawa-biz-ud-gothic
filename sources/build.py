from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import _c_m_a_p
from fontTools import merge
from pathlib import Path
import glob
import fontmake.__main__
import os, shutil, subprocess

# Morisawa UD font merging script
# For these particular fonts, we have chosen to preserve the existing TTFs as delivered directly from Morisawa, and merge the additional glyphs via a build script. 
# 
# This script converts the "extensions" Glyphs file to TTF, autohints it, and then merges it into the existing TTF file via psftmerge. There's some oddities in this process which have to be solved in post-production at the end of the process due to tables getting dropped / metadata being set differently.

IMPORT = Path('sources/ttf')
TEMP = Path('fonts/temp')
EXPORT = Path('fonts/ttf')
SRC_IMPORT = Path("sources/extensions")

for font in IMPORT.glob("*.ttf"):
    
    # Step 1 - create ttf for extension to the font
    fontName = str(font).split("/")[2]
    sourceTTF = TTFont(font)

    fontmake.__main__.main([
        "-g", str(SRC_IMPORT / str(fontName[:-4]+"Ext.glyphs")), 
        "-o", "ttf",
        "--output-dir",
        str(TEMP),
        ])
    
    if "Bold" in fontName:
        extSource = str(TEMP / str(fontName[:-4].replace("-Bold","Ext-Bold"+".ttf")))
        outputTTF = str(fontName)
    else:
        extSource = str(TEMP / str(fontName[:-4]+"Ext-Regular.ttf"))
        outputTTF = str(fontName[:-4]+"-Regular.ttf")


    # For some reason, the autohinter built into fontmake is not working, so I'm doing it separately here which works
    subprocess.check_call(
        [
            "ttfautohint",
            "--symbol",
            "--reference="+str(font),
            extSource,
            extSource[:-4] + "-hinted.ttf",
        ]
    )

    # Here I'm stripping the .notdef chararter to avoid it showing up in the final font
    subprocess.check_call(
        [
            "pyftsubset",
            extSource[:-4] + "-hinted.ttf",
            "--glyphs=*"
        ]
    )

    shutil.move(extSource[:-4] + "-hinted.subset.ttf", extSource)
    os.remove(extSource[:-4] + "-hinted.ttf")

    # Step 2 - Some metadata changes to align with GF expectations
    # NAME table modifications
    sourceTTF["name"].removeNames(platformID=1)
    sourceTTF["name"].removeNames(nameID=6,platformID=3, langID=1041)

    versionString = sourceTTF["head"].fontRevision
    for platformID in [1033, 1041]:
        name = sourceTTF["name"].getDebugName(1)

        sourceTTF["name"].setName("Copyright 2022 The BIZ UDGothic Project Authors (https://github.com/googlefonts/morisawa-biz-ud-gothic)",0,3,1,platformID)
        sourceTTF["name"].setName(name,1,3,1,platformID)

        if "Bold" in fontName: #aligning psnames with google standards. Shouldn't impact compatibility.
            sourceTTF["name"].setName(name.replace("BIZ ","BIZ")+"-Bold",6,3,1,platformID)
        else:
            sourceTTF["name"].setName(name.replace("BIZ ","BIZ")+"-Regular",6,3,1,platformID)

        sourceTTF["name"].setName("Version "+str(versionString),5,3,1,platformID)
        if platformID == 1033:        
            sourceTTF["name"].setName(name+" is a trademark of Morisawa Inc.",7,3,1,platformID)
            sourceTTF["name"].setName("This Font Software is licensed under the SIL Open Font License, Version 1.1. This license is available with a FAQ at: https://scripts.sil.org/OFL",13,3,1,platformID)
            sourceTTF["name"].setName("https://scripts.sil.org/OFL",14,3,1,platformID)

    # OS/2 Table modifications
    versionString = sourceTTF["OS/2"].fsType = 0

    #Step 4 - Export updated source version
    sourceTTF.save(TEMP / outputTTF)

    # Step 5 - Merge source with extentions

    subprocess.check_call(
        [
            "pyftmerge",
            str(TEMP/outputTTF),
            str(extSource),
            "--output-file="+str(EXPORT / str(outputTTF).replace("BIZ-","BIZ")),
        ]
    )
    
    # Due to merging, some things get messed up:
        # The meta table is dropped
        # the Unicode cmap tables are dropped
        # fixedPitch set incorrectly
        # also tweaks to OS/2 and head also necessary to match original

    finalVersion = TTFont(str(EXPORT / str(outputTTF).replace("BIZ-","BIZ")))
    finalVersion["meta"] = sourceTTF["meta"]

    cmap0_3_4 = _c_m_a_p.CmapSubtable.newSubtable(4)

    cmap0_3_4.platformID = 0
    cmap0_3_4.platEncID = 3
    cmap0_3_4.language = 0

    cmap0_3_4.cmap = finalVersion["cmap"].getcmap(3,1).cmap #copying from merged version

    finalVersion["cmap"].tables.append(cmap0_3_4)
    finalVersion["cmap"].tables.append(sourceTTF["cmap"].getcmap(0,5))

    if "P" not in fontName:
        finalVersion["post"].isFixedPitch = 1
        finalVersion["OS/2"].panose.bProportion = 9
        
    finalVersion["head"].flags = 0x000b

    newDSIG = newTable("DSIG")
    newDSIG.ulVersion = 1
    newDSIG.usFlag = 0
    newDSIG.usNumSigs = 0
    newDSIG.signatureRecords = []
    finalVersion.tables["DSIG"] = newDSIG

    # Irritatingly, pyftmerge does not calculate the average character width correctly. It appears to simply average the xAvgCharWidth value in the two font files. However, given the heavy weighting of wider Japanese characters, we need to recalculate the average and insert it back into the font. 

    width_sum = 0
    count = 0
    for glyph_id in finalVersion['glyf'].glyphs:  # At least .notdef must be present.
        width = finalVersion['hmtx'].metrics[glyph_id][0]
        # The OpenType spec doesn't exclude negative widths, but only positive
        # widths seems to be the assumption in the wild?
        if width > 0:
            count += 1
            width_sum += width

    avgCharWidth = int(round(width_sum / count))
    finalVersion["OS/2"].xAvgCharWidth = avgCharWidth

    finalVersion.save(EXPORT / str(outputTTF).replace("BIZ-","BIZ"))

shutil.rmtree("fonts/temp")
shutil.rmtree("master_ufo")
shutil.rmtree("instance_ufo")