package ComponentModel1 {

    port def CppAlias;
    port def CppCalls;
    port def CppContains;
    port def CppImplements;
    port def CppInherits;
    port def CppUses;
    port def Include;
    port def Name;
    port def ParentFolder;
    port def ProjectCompilesNested;
    port def Source;

    part def CppDeclaration {
        port serverCppAlias : CppAlias;
        port clientCppAlias : CppAlias;
        port clientCppContains : CppContains;
        port clientCppInherits : CppInherits;
        port clientSource : Source;
    }

    part def CppFunctionDeclaration {
        port serverCppCalls : CppCalls;
        port serverCppContains : CppContains;
        port serverCppImplements : CppImplements;
        port serverCppUses : CppUses;
        port clientName : Name;
        port clientSource : Source;
    }

    part def CppFunctionDefinition {
        port serverCppCalls : CppCalls;
        port serverCppContains : CppContains;
        port serverCppImplements : CppImplements;
        port serverCppUses : CppUses;
        port clientCppCalls : CppCalls;
        port clientCppImplements : CppImplements;
        port clientName : Name;
        port clientSource : Source;
    }

    part def CppForwardDeclaration {
        port serverCppInherits : CppInherits;
        port serverCppUses : CppUses;
        port clientName : Name;
    }

    part def CppMacroDefinition {
        port serverCppUses : CppUses;
        port clientName : Name;
    }

    part def Symbol {
        port serverName : Name;
    }

    part def HeaderFile {
        port serverInclude : Include;
        port serverProjectCompilesNested : ProjectCompilesNested;
        port serverSource : Source;
        port clientInclude : Include;
        port clientCppUses : CppUses;
        port clientParentFolder : ParentFolder;
    }

    part def OtherFile {
        port serverInclude : Include;
        port serverProjectCompilesNested : ProjectCompilesNested;
        port serverSource : Source;
        port clientInclude : Include;
        port clientCppUses : CppUses;
        port clientParentFolder : ParentFolder;
    }

    part def SourceFile {
        port serverProjectCompilesNested : ProjectCompilesNested;
        port serverSource : Source;
        port clientInclude : Include;
        port clientCppUses : CppUses;
        port clientParentFolder : ParentFolder;
    }

    part def Folder {
        port serverParentFolder : ParentFolder;
    }

    part def DynamicLinkLibrary {
        port clientParentFolder : ParentFolder;
    }

    part def Executable {
        port clientParentFolder : ParentFolder;
    }

    part def ProjectCOrCpp {
        port clientParentFolder : ParentFolder;
        port serverProjectCompilesNested : ProjectCompilesNested;
    }

    part def ProjectPropertySheet {
        port clientParentFolder : ParentFolder;
    }

    part def Solution {
        port clientParentFolder : ParentFolder;
    }

    part def System {
        part cppdeclaration : CppDeclaration;
        part cppfunctiondeclaration : CppFunctionDeclaration;
        part cppfunctiondefinition : CppFunctionDefinition;
        part cppforwarddeclaration : CppForwardDeclaration;
        part cppmacrodefinition : CppMacroDefinition;
        part symbol : Symbol;
        part headerfile : HeaderFile;
        part otherfile : OtherFile;
        part sourcefile : SourceFile;
        part folder : Folder;
        part dynamiclinklibrary : DynamicLinkLibrary;
        part executable : Executable;
        part projectcorcpp : ProjectCOrCpp;
        part projectpropertysheet : ProjectPropertySheet;
        part solution : Solution;

        connect cppdeclaration.serverCppAlias to cppdeclaration.clientCppAlias;
        connect cppfunctiondeclaration.serverCppCalls to cppfunctiondefinition.clientCppCalls;
        connect cppfunctiondefinition.serverCppCalls to cppfunctiondefinition.clientCppCalls;
        connect cppdeclaration.serverCppContains to cppdeclaration.clientCppContains;
        connect cppfunctiondeclaration.serverCppContains to cppdeclaration.clientCppContains;
        connect cppfunctiondefinition.serverCppContains to cppdeclaration.clientCppContains;
        connect cppfunctiondeclaration.serverCppImplements to cppfunctiondefinition.clientCppImplements;
        connect cppfunctiondefinition.serverCppImplements to cppfunctiondefinition.clientCppImplements;
        connect cppdeclaration.serverCppInherits to cppdeclaration.clientCppInherits;
        connect cppforwarddeclaration.serverCppInherits to cppdeclaration.clientCppInherits;

        connect cppdeclaration.serverCppUses to headerfile.clientCppUses;
        connect cppforwarddeclaration.serverCppUses to headerfile.clientCppUses;
        connect cppfunctiondeclaration.serverCppUses to headerfile.clientCppUses;
        connect cppfunctiondefinition.serverCppUses to headerfile.clientCppUses;
        connect cppmacrodefinition.serverCppUses to headerfile.clientCppUses;

        connect headerfile.serverInclude to headerfile.clientInclude;
        connect otherfile.serverInclude to headerfile.clientInclude;
        connect headerfile.serverInclude to otherfile.clientInclude;
        connect otherfile.serverInclude to otherfile.clientInclude;
        connect headerfile.serverInclude to sourcefile.clientInclude;
        connect otherfile.serverInclude to sourcefile.clientInclude;

        connect symbol.serverName to cppdeclaration.clientName;
        connect symbol.serverName to cppforwarddeclaration.clientName;
        connect symbol.serverName to cppfunctiondeclaration.clientName;
        connect symbol.serverName to cppfunctiondefinition.clientName;
        connect symbol.serverName to cppmacrodefinition.clientName;

        connect folder.serverParentFolder to dynamiclinklibrary.clientParentFolder;
        connect folder.serverParentFolder to executable.clientParentFolder;
        connect folder.serverParentFolder to folder.clientParentFolder;
        connect folder.serverParentFolder to headerfile.clientParentFolder;
        connect folder.serverParentFolder to otherfile.clientParentFolder;
        connect folder.serverParentFolder to projectcorcpp.clientParentFolder;
        connect folder.serverParentFolder to projectpropertysheet.clientParentFolder;
        connect folder.serverParentFolder to solution.clientParentFolder;
        connect folder.serverParentFolder to sourcefile.clientParentFolder;

        connect headerfile.serverProjectCompilesNested to projectcorcpp.clientProjectCompilesNested;
        connect otherfile.serverProjectCompilesNested to projectcorcpp.clientProjectCompilesNested;
        connect sourcefile.serverProjectCompilesNested to projectcorcpp.clientProjectCompilesNested;

        connect headerfile.serverSource to cppdeclaration.clientSource;
        connect otherfile.serverSource to cppdeclaration.clientSource;
        connect sourcefile.serverSource to cppdeclaration.clientSource;
        connect headerfile.serverSource to cppfunctiondeclaration.clientSource;
        connect otherfile.serverSource to cppfunctiondeclaration.clientSource;
        connect sourcefile.serverSource to cppfunctiondeclaration.clientSource;
        connect headerfile.serverSource to cppfunctiondefinition.clientSource;
        connect otherfile.serverSource to cppfunctiondefinition.clientSource;
        connect sourcefile.serverSource to cppfunctiondefinition.clientSource;

    }
}
