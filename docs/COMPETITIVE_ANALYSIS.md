# PreFlight: Competitive & Privacy Analysis

*Last updated: January 2025*

---

## NVIDIA Nemotron Analysis

### Executive Summary

**Nemotron is NOT a competitor - it's a potential customer and integration partner.**

PreFlight and Nemotron operate at **different layers** of the document processing stack:

```
Layer 4: Business Application (ERP, CRM, etc.)
Layer 3: GOVERNANCE (PreFlight) ← We are here
Layer 2: EXTRACTION (Nemotron, Azure Doc AI, AWS Textract) ← They are here
Layer 1: Document Storage (S3, blob storage)
```

### Nemotron Model Family

Based on [NVIDIA's documentation](https://developer.nvidia.com/nemotron):

| Model | Purpose | Key Capability |
|-------|---------|----------------|
| **Nemotron Parse 1.1** | Document parser | Extracts text, tables with bounding boxes (1B params) |
| **Nemotron Nano 2 VL** | Multimodal reasoning | Document intelligence, OCR, 12B params |
| **Llama Nemotron Nano VL** | Production OCR | Invoice/receipt/contract extraction, 8B params |
| **Nemotron 3 Nano** | Long-context reasoning | 1M token context, JSON schema adherence |

**Nemotron capabilities:**
- OCR (leading on [OCRBench v2](https://developer.nvidia.com/blog/new-nvidia-llama-nemotron-nano-vision-language-model-tops-ocr-benchmark-for-accuracy/))
- Table extraction, chart parsing
- Visual Q&A on documents
- JSON schema adherence for structured output

### Feature Comparison

| Feature | PreFlight | Nemotron |
|---------|-----------|----------|
| Document extraction | Never | Core feature |
| Sees document content | Never (metadata only) | Yes |
| Template matching | Core feature | No |
| Drift detection | Core feature | No |
| Reliability scoring | Core feature | No |
| Multi-extractor governance | Core feature | N/A |
| Correction rules | Core feature | No |
| Audit trail | Core feature | Limited |
| PII handling | Never touches | Must handle |

### Why Nemotron is NOT a Threat

1. **Different problem space**: Nemotron extracts data. PreFlight governs extraction pipelines. They're complementary.

2. **Nemotron creates MORE need for PreFlight**: As enterprises adopt Nemotron (and other extractors), they need:
   - A way to compare Nemotron vs. other extractors per document type
   - Detection when document layouts drift over time
   - Routing logic to pick the right extractor for each document
   - Audit trails for compliance

3. **No governance features**: Nemotron doesn't provide:
   - Template versioning and matching
   - Drift detection over time
   - Extractor reliability comparison
   - Correction rule selection
   - Compliance audit trails

4. **PII/compliance concern**: Enterprises can't send all documents to cloud extractors. PreFlight's metadata-only approach solves compliance requirements.

### Integration Opportunity

Our `ExtractorMetadata.vendor` field already accepts "nvidia" as a value (see `src/models.py:203`).

**Integration flow:**
```
Customer Document → Nemotron (extracts text, tables, confidence)
                 ↓
Nemotron Output → Customer extracts METADATA (fingerprint, element counts)
                 ↓
Metadata Only → PreFlight (template match, drift, reliability, rules)
                 ↓
Governance Decision → Customer applies correction rules
```

### Strategic Opportunities

| Option | Description | Benefit |
|--------|-------------|---------|
| **A: Reference extractor** | Include Nemotron benchmarks in reliability scoring | "Your extractor: 0.65. Nemotron: 0.92 for this template." |
| **B: Parse integration** | Use Nemotron Parse output for fingerprinting | Better structural features = better matching |
| **C: Partnership** | Position PreFlight as governance for Nemotron deployments | "Every Nemotron user needs PreFlight" |

### Founder's Verdict

**The MORE extractors exist (Nemotron, Azure Doc AI, AWS Textract, Google Doc AI), the MORE valuable PreFlight becomes.**

---

## Privacy-Enhancing Technologies: Beyond Metadata-Only

### Current Approach: Metadata-Only

PreFlight's metadata-only approach is the **simplest and most trustworthy** privacy solution today:
- Zero PII exposure (we never see document content)
- No trust required in encryption/hardware
- Simple compliance story ("we don't have your data")
- Works with any extractor

**But it's not the only approach.** Here's what's emerging:

### Alternative Privacy Technologies (2025 State of Art)

| Technology | How It Works | Maturity | Performance | Trust Model |
|------------|--------------|----------|-------------|-------------|
| **Metadata-only** (current) | Never see content | Production | Native | Zero trust needed |
| **Secure Enclaves (TEE)** | Hardware-isolated execution | Production | Near-native | Trust CPU vendor |
| **Differential Privacy** | Add calibrated noise | Production | Good | Mathematical proof |
| **Homomorphic Encryption** | Compute on encrypted data | Emerging | 1000x slower | Mathematical proof |
| **Federated Learning** | Model trains on-premise | Production | Good | Trust aggregation |

### Detailed Analysis

#### 1. Secure Enclaves / Confidential Computing (TEE)

Based on [Duality Technologies](https://dualitytech.com/blog/confidential-computing-tees-what-enterprises-must-know-in-2025/):
- Intel SGX, AMD SEV, AWS Nitro Enclaves, Azure Confidential
- Data processed in isolated CPU region - even cloud provider can't see it
- **Near-native performance** (slight latency from enclave transitions)
- **Production-ready** - used by healthcare for multi-party analytics

**PreFlight opportunity**: Deploy governance logic in TEE for customers who want deeper content analysis with privacy guarantees.

#### 2. Differential Privacy

Based on [privacy research](https://www.navicat.com/en/company/aboutus/blog/3405-privacy-preserving-databases-protecting-data-while-enabling-access.html):
- Add mathematical noise to results
- Guarantees: "Whether your data is included or not, outputs are indistinguishable"
- **Already used by** Apple (keyboard data), Google (Chrome), US Census

**PreFlight opportunity**: Accept differentially-private aggregates from customer-side processing for analytics without raw data.

#### 3. Fully Homomorphic Encryption (FHE)

Based on [GoCodeo research](https://www.gocodeo.com/post/exploring-use-cases-of-fully-homomorphic-encryption-in-2025):
- Compute on encrypted data without decryption
- **Roche uses FHE** for encrypted patient data analysis
- Currently **1000x slower** than plaintext, improving rapidly
- Hardware-independent (unlike TEE)

**PreFlight opportunity**: Long-term option for ultimate privacy, but performance not viable for real-time governance yet.

#### 4. Federated Learning

Based on [Google Cloud](https://cloud.google.com/architecture/security/confidential-computing-analytics-ai):
- Model trains on customer premises
- Only model weights/gradients leave customer
- Combined with TEE for secure aggregation

**PreFlight opportunity**: On-premise PreFlight agent that learns template patterns locally, syncs only aggregate patterns to cloud.

### Strategic Roadmap for PreFlight

| Phase | Technology | Use Case | Timeline |
|-------|------------|----------|----------|
| **Now** | Metadata-only | Core governance | Current |
| **Near-term** | TEE (AWS Nitro) | Content-aware drift for high-security customers | 6-12 months |
| **Mid-term** | Differential Privacy | Analytics dashboard without raw metrics | 12-18 months |
| **Long-term** | FHE | Ultimate privacy compute | 2-3 years |

### Why Metadata-Only Remains Primary

1. **Simplest compliance**: "We don't have your data" beats "we have it but it's encrypted"
2. **No hardware trust**: TEE requires trusting Intel/AMD/cloud provider
3. **Universal compatibility**: Works with any extractor, any customer infrastructure
4. **Performance**: No encryption overhead, no enclave transitions

### When to Evolve Beyond Metadata

Customers may need more than metadata when they want:
- **Content-aware drift**: "The vendor name field changed from 'Acme Corp' to 'ACME CORPORATION'"
- **Semantic template matching**: Understanding document meaning, not just structure
- **Field-level reliability**: Confidence per extracted field, not just document-level

**For these cases**, TEE deployment is the most practical near-term solution.

---

## Sources

- [NVIDIA Nemotron Models](https://developer.nvidia.com/nemotron)
- [Nemotron Parse 1.1](https://developer.nvidia.com/blog/turn-complex-documents-into-usable-data-with-vlm-nvidia-nemotron-parse-1-1/)
- [Nemotron OCR Benchmarks](https://developer.nvidia.com/blog/new-nvidia-llama-nemotron-nano-vision-language-model-tops-ocr-benchmark-for-accuracy/)
- [Duality Technologies - Confidential Computing](https://dualitytech.com/blog/confidential-computing-tees-what-enterprises-must-know-in-2025/)
- [Google Cloud - Confidential Computing for AI](https://cloud.google.com/architecture/security/confidential-computing-analytics-ai)
- [FHE Use Cases 2025](https://www.gocodeo.com/post/exploring-use-cases-of-fully-homomorphic-encryption-in-2025)
