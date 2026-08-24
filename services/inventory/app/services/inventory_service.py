@@
     existing = get_inventory(
         db,
         inventory.sku_id,
         inventory.warehouse_id,
     )
 
-    if existing:
-        return None
+    if existing:
+        raise InventoryOperationError("Inventory already exists")
@@
     db.add(item)
 
-    db.commit()
-
-    db.refresh(item)
-
-
-    return inventory_response(item)
+    db.commit()
+
+    db.refresh(item)
+
+
+    return inventory_response(item)
