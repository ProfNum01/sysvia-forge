# ProofSight demo script (maximum 180 seconds)

**Evidence basis:** Two live Meta inspections of existing SYNTHETIC packing scenes on November 1, 2026. Both returned `NEEDS_REVIEW`. The after images have not received live inference. A separate existing synthetic fixture has a persisted before/after workflow; it is not physical validation.

| Time | Screen | Voiceover |
|---|---|---|
| 00:00–00:20 | Order manifest and packing scene | “A digital order says what should be packed. ProofSight checks what the image can actually support before shipment.” |
| 00:20–00:45 | Demo Workspace, select `PACK-MISSING` | “These four supplied scenes form two synthetic before and after pairs. The packing products use a separate catalog because the older reference images depict different objects.” |
| 00:45–01:20 | Visual Inspection, before image and persisted result | “A local quality gate checks resolution and exposure before paid inference. Muse Spark 1.3 and SAM 3.1 then inspect the scene. The products have no readable SKU labels, so color and shape alone cannot prove exact identity. This live result requires review.” |
| 01:20–01:55 | AI Operations, tool timeline | “The agent used five bounded read tools to inspect the order, inventory, and evidence. Its recommendation is recorded. Server policy permits only validated proposals, with human approval for consequential actions.” |
| 01:55–02:25 | Action state and held shipping | “The order remains held. An operator may review a proposed action; completing a physical task never counts as visual verification.” |
| 02:25–02:45 | Show supplied after image, clearly labeled uninspected | “The supplied after photo depicts the intended synthetic correction, but it has not been live re-inspected. A new photo and a separate model result are required to verify any correction.” |
| 02:45–03:00 | Benchmark summary | “Across two live synthetic cases, inspection latency was 19.253 and 18.743 seconds. Both were escalated safely; no false verification or shipping safety violation was observed in this small sample.” |

**Recording rule:** Show actual persisted results. Do not imply the after images, physical correction, or an approval flow were live validated in this sprint. Do not show credentials.
