"""Label printing endpoints (product labels + cut labels)."""

import logging
import os

from flask import Blueprint, current_app, jsonify, request

from ...tspl.label_builder import build_tspl_label
from ...tspl.cut_label_builder import build_tspl_cut_label

bp = Blueprint("labels", __name__)
logger = logging.getLogger("printbridge")


@bp.route("/api/print-labels", methods=["POST"])
def print_labels():
    """Print product labels using native TSPL commands (no PDF)."""
    try:
        data = request.get_json()
        if not data or "labels" not in data:
            return jsonify({"error": 'Missing "labels" array'}), 400

        labels = data["labels"]
        if not isinstance(labels, list) or len(labels) == 0:
            return jsonify({"error": '"labels" must be a non-empty array'}), 400

        printer_name = data.get("printer", None)
        label_width = int(data.get("labelWidth", 100))
        label_height = int(data.get("labelHeight", 150))
        shop_name = data.get("shopName", "")
        work_order_id = data.get("workOrderId", 0)
        qr_base_url = data.get("qrBaseUrl", "")
        copies = int(data.get("copies", 1))
        display_options = data.get("displayOptions", {})

        config = current_app.config["PRINTBRIDGE_CONFIG"]

        if copies < 1 or copies > 99:
            return jsonify({"error": "Copies must be between 1 and 99"}), 400

        all_commands = []
        total_labels = 0

        for label in labels:
            qty = int(label.get("quantity", 1))
            measurement_id = label.get("measurementId", "")
            sig = label.get("sig", "")

            qr_url = ""
            if qr_base_url and measurement_id:
                qr_url = f"{qr_base_url}{measurement_id}"
                if sig:
                    qr_url += f"?sig={sig[:16]}"

            for _ in range(qty):
                for _ in range(copies):
                    tspl = build_tspl_label(
                        product_name=label.get("productName", "Product"),
                        formule_name=label.get("formuleName", ""),
                        width=label.get("width", 0),
                        height=label.get("height", 0),
                        position=label.get("position", ""),
                        quantity=qty,
                        order_ref=label.get("orderRef", ""),
                        client_name=label.get("clientName", ""),
                        qr_url=qr_url,
                        shop_name=shop_name,
                        work_order_id=work_order_id,
                        label_width_mm=label_width,
                        label_height_mm=label_height,
                        display_options=display_options,
                        footer_text=config.footer_text,
                    )
                    all_commands.append(tspl)
                    total_labels += 1

        batch = b"".join(all_commands)
        logger.info(f"TSPL batch: {total_labels} labels, {len(batch)} bytes")

        if os.environ.get("PRINTBRIDGE_DEBUG"):
            debug_path = config.log_path / "debug_tspl.bin"
            try:
                debug_path.write_bytes(batch)
                logger.info(f"TSPL debug saved to {debug_path}")
            except Exception as e:
                logger.warning(f"Could not save debug TSPL: {e}")

        backend = current_app.config["PRINTBRIDGE_BACKEND"]
        backend.send_raw(batch, printer_name)

        return jsonify({
            "success": True,
            "printer": printer_name or backend.get_default_printer(),
            "totalLabels": total_labels,
            "method": "tspl",
        })

    except Exception as e:
        logger.error(f"Print labels route error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route("/api/print-cut-labels", methods=["POST"])
def print_cut_labels():
    """Print cut labels using native TSPL commands (no PDF)."""
    try:
        data = request.get_json()
        if not data or "labels" not in data:
            return jsonify({"error": 'Missing "labels" array'}), 400

        labels = data["labels"]
        if not isinstance(labels, list) or len(labels) == 0:
            return jsonify({"error": '"labels" must be a non-empty array'}), 400

        printer_name = data.get("printer", None)
        label_width = int(data.get("labelWidth", 45))
        label_height = int(data.get("labelHeight", 35))
        shop_name = data.get("shopName", "")
        order_ref = data.get("orderRef", "")
        copies = int(data.get("copies", 1))

        config = current_app.config["PRINTBRIDGE_CONFIG"]

        if copies < 1 or copies > 99:
            return jsonify({"error": "Copies must be between 1 and 99"}), 400

        all_commands = []
        total_labels = 0

        for i, label in enumerate(labels):
            for copy_n in range(copies):
                tspl = build_tspl_cut_label(
                    position=label.get("position", ""),
                    bar_info=label.get("barInfo", ""),
                    profile_name=label.get("profileName", ""),
                    profile_ref=label.get("profileRef", ""),
                    cut_name=label.get("cutName", ""),
                    finishing=label.get("finishing", ""),
                    length=int(label.get("length", 0)),
                    angles=label.get("angles", ""),
                    quantity=1,
                    bin_number=int(label.get("binNumber", 0)),
                    shop_name=shop_name,
                    label_width_mm=label_width,
                    label_height_mm=label_height,
                    order_ref=order_ref,
                    source=label.get("source", ""),
                    footer_text=config.footer_text,
                )
                all_commands.append(tspl)
                total_labels += 1

        batch = b"".join(all_commands)
        logger.info(f"[print-cut-labels] batch ready: {total_labels} labels, {len(batch)} bytes total")

        if os.environ.get("PRINTBRIDGE_DEBUG"):
            debug_path = config.log_path / "debug_cut_labels.tspl"
            try:
                debug_path.write_bytes(batch)
            except Exception as e:
                logger.warning(f"Could not save debug dump: {e}")

        backend = current_app.config["PRINTBRIDGE_BACKEND"]
        backend.send_raw(batch, printer_name)

        return jsonify({
            "success": True,
            "printer": printer_name or backend.get_default_printer(),
            "totalLabels": total_labels,
            "method": "tspl",
        })

    except Exception as e:
        logger.error(f"Print cut labels route error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
