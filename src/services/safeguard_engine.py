"""Safeguard engine for validating extraction metadata.

Provides validation rules for:
- Data completeness checks
- Layout consistency verification
- Provider-specific validation
- Anomaly detection
"""

from src.models import ExtractorMetadata, ExtractorProvider, StructuralFeatures


class SafeguardEngine:
    """Validates extraction metadata before processing."""

    def validate_request(
        self,
        features: StructuralFeatures,
        extractor: ExtractorMetadata,
        provider: ExtractorProvider | None,
    ) -> list[str]:
        """
        Validate extraction request and return list of warnings/errors.

        Args:
            features: Structural features from document
            extractor: Metadata about the extraction provider
            provider: Provider configuration from DB (None if unknown)

        Returns:
            List of warning/error strings. Empty list = valid request.
            Strings prefixed with "ERROR:" indicate critical issues.
            Strings prefixed with "WARN:" indicate non-blocking warnings.
        """
        issues: list[str] = []

        # 1. Data Completeness
        issues.extend(self._check_completeness(features))

        # 2. Layout Consistency
        issues.extend(self._check_layout_consistency(features))

        # 3. Provider-Specific Checks
        if provider:
            issues.extend(self._check_provider_specific(features, extractor, provider))

        # 4. Anomaly Detection
        issues.extend(self._check_anomalies(features, extractor))

        return issues

    def _check_completeness(self, features: StructuralFeatures) -> list[str]:
        """Check for missing or incomplete data."""
        issues: list[str] = []

        if not features.bounding_boxes:
            issues.append("WARN: No bounding boxes provided - layout matching will be limited")

        if features.element_count == 0:
            issues.append("ERROR: Zero elements detected - extraction may have failed completely")

        if features.page_count == 0:
            issues.append("ERROR: Zero pages reported - invalid document structure")

        # Check for inconsistent counts
        bbox_count = len(features.bounding_boxes)
        if bbox_count > 0 and features.element_count > 0:
            ratio = bbox_count / features.element_count
            if ratio < 0.1:
                issues.append(
                    f"WARN: Only {bbox_count} bounding boxes for {features.element_count} elements "
                    f"({ratio:.1%}) - layout data may be incomplete"
                )

        return issues

    def _check_layout_consistency(self, features: StructuralFeatures) -> list[str]:
        """Check for layout issues in bounding boxes."""
        issues: list[str] = []
        zero_area_count = 0
        out_of_bounds_count = 0

        for i, bbox in enumerate(features.bounding_boxes):
            # Check for zero-area boxes
            if bbox.width == 0 or bbox.height == 0:
                zero_area_count += 1
                if zero_area_count <= 3:
                    issues.append(f"WARN: Zero-area bounding box at index {i}")

            # Check for out-of-bounds coordinates
            if bbox.x + bbox.width > 1.01 or bbox.y + bbox.height > 1.01:
                out_of_bounds_count += 1
                if out_of_bounds_count <= 3:
                    issues.append(f"WARN: Bounding box {i} exceeds normalized page bounds")

            # Check for negative coordinates (shouldn't happen with Pydantic validation)
            if bbox.x < 0 or bbox.y < 0:
                issues.append(f"WARN: Bounding box {i} has negative coordinates")

        # Summarize if many issues
        if zero_area_count > 3:
            issues.append(f"WARN: {zero_area_count} total zero-area bounding boxes detected")
        if out_of_bounds_count > 3:
            issues.append(f"WARN: {out_of_bounds_count} total out-of-bounds bounding boxes detected")

        # Check for suspicious layout metrics
        if features.layout_complexity > 0.95:
            issues.append("WARN: Extremely high layout complexity (>0.95) - document may be corrupted")

        if features.text_density == 0 and features.text_block_count > 0:
            issues.append("WARN: Text density is 0 but text blocks exist - check density calculation")

        return issues

    def _check_provider_specific(
        self,
        features: StructuralFeatures,
        extractor: ExtractorMetadata,
        provider: ExtractorProvider,
    ) -> list[str]:
        """Provider-specific validation rules."""
        issues: list[str] = []

        # Check element types match provider's supported types
        if provider.supported_element_types:
            supported_lower = {t.lower() for t in provider.supported_element_types}
            unknown_types: set[str] = set()

            for bbox in features.bounding_boxes:
                if bbox.element_type.lower() not in supported_lower:
                    unknown_types.add(bbox.element_type)

            if unknown_types:
                types_str = ", ".join(sorted(unknown_types)[:5])
                if len(unknown_types) > 5:
                    types_str += f" (+{len(unknown_types) - 5} more)"
                issues.append(
                    f"WARN: Unknown element types for {provider.display_name}: {types_str}"
                )

        # Check latency is reasonable
        if provider.typical_latency_ms > 0:
            if extractor.latency_ms > provider.typical_latency_ms * 3:
                issues.append(
                    f"WARN: Latency {extractor.latency_ms}ms is 3x typical "
                    f"({provider.typical_latency_ms}ms) for {provider.display_name}"
                )
            elif extractor.latency_ms < provider.typical_latency_ms * 0.1:
                issues.append(
                    f"WARN: Latency {extractor.latency_ms}ms is unusually low "
                    f"for {provider.display_name} (typical: {provider.typical_latency_ms}ms)"
                )

        # Provider-specific confidence checks
        if provider.confidence_multiplier != 1.0:
            calibrated = extractor.confidence * provider.confidence_multiplier
            if calibrated > 1.0:
                issues.append(
                    f"WARN: After calibration, confidence would exceed 1.0 "
                    f"({extractor.confidence} * {provider.confidence_multiplier} = {calibrated:.2f})"
                )

        return issues

    def _check_anomalies(
        self,
        features: StructuralFeatures,
        extractor: ExtractorMetadata,
    ) -> list[str]:
        """Detect anomalous patterns that might indicate issues."""
        issues: list[str] = []

        # Low confidence with many elements
        if extractor.confidence < 0.5 and features.element_count > 100:
            issues.append(
                f"WARN: Low confidence ({extractor.confidence:.2f}) with many elements "
                f"({features.element_count}) - review recommended"
            )

        # High confidence with very few elements
        if extractor.confidence > 0.95 and features.element_count < 5:
            issues.append(
                f"WARN: Very high confidence ({extractor.confidence:.2f}) with few elements "
                f"({features.element_count}) - may be incomplete extraction"
            )

        # Suspiciously perfect metrics
        if extractor.confidence == 1.0:
            issues.append("WARN: Perfect confidence score (1.0) is unusual - verify extraction")

        # Multi-page with no tables might indicate scan issues
        if features.page_count > 10 and features.table_count == 0 and features.text_block_count < 50:
            issues.append(
                f"WARN: {features.page_count} pages with no tables and few text blocks "
                f"({features.text_block_count}) - possible scan/extraction failure"
            )

        # Check for reasonable column count
        if features.column_count > 10:
            issues.append(
                f"WARN: Unusually high column count ({features.column_count}) - "
                "verify layout detection"
            )

        return issues


# Singleton instance for convenience
safeguard_engine = SafeguardEngine()
