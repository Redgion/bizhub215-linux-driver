# Licensing and provenance

This independently written implementation is offered under GPL-2.0-or-later.
The complete license is in LICENSE. JBIG compression comes from the system's
JBIG-KIT library, not from a Windows DLL. Preserve its license obligations and
provide the corresponding source and build scripts when distributing binaries.
Our release source archive supplies our implementation and build scripts;
the system library is obtained separately from the distribution.

Development used static inspection of the ONG8-family Windows GDI driver to
identify framing commands, binary lengths and the JBIG profile, followed by
native implementation and local/hardware experiments. No vendor executable,
font, manual, decompiled listing or translated proprietary function is shipped.
The same development agent examined the binary and implemented the protocol;
this was not a separated clean-room process. We do not claim otherwise.

Similarity of required protocol bytes is needed for interoperability. Renaming
variables, reformatting code or achieving a low similarity percentage does not
establish copyright clearance. We must avoid copying protected implementation,
not artificially alter required device commands.

GPL grants rights only to material that its licensors may license. It neither
relicenses the Windows driver nor overrides its agreement. The inspected vendor
installer contains a restriction on reverse analysis and a Japanese governing-law
clause. Statutory interoperability/research exceptions can apply subject to their
conditions; their application to this project has not been legally adjudicated.
Public release is not represented as legal clearance from the vendor.

Relevant primary sources:
- [JBIG-KIT author: licensing](https://www.cl.cam.ac.uk/~mgk25/jbigkit/).
- [GNU: GPL libraries](https://www.gnu.org/licenses/gpl-faq.en.html#IfLibraryIsGPL).
- [EU Directive 2009/24/EC, especially Article 6](https://eur-lex.europa.eu/LexUriServ/LexUriServ.do?uri=OJ%3AL%3A2009%3A111%3A0016%3A0022%3AEN%3APDF).
- [Japanese Agency for Cultural Affairs: research exceptions](https://www.bunka.go.jp/seisaku/chosakuken/hokaisei/h30_hokaisei/).
- [Russian Civil Code, WIPO Lex](https://www.wipo.int/wipolex/en/legislation/details/23256).

Konica Minolta and bizhub identify the supported product. No affiliation,
endorsement, permission from the vendor, or exclusive rights over its protocol
are claimed. AI assistance does not establish exclusive ownership of generated
material or guarantee absence of third-party rights.
