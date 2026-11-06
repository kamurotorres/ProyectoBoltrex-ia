import React from 'react';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Loader2, Package, Plus, Search, ShoppingBag, Trash2, Truck } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

// Extraído de Purchases.js (mantenimiento fase 5) sin cambios en el JSX.
export default function PurchaseDialog({ addProductToItems, calculateTotal, dialogDesc, dialogMode, dialogOpen, dialogTitle, filteredProducts, filteredSuppliers, handleCloseDialog, handleSelectSupplier, handleSubmit, isReadonly, isSubmitting, items, productInputRef, productSearch, removeItem, selectedSupplier, setDialogOpen, setItemQuantity, setItems, setProductSearch, setSelectedSupplier, setShowProductDropdown, setShowSupplierDropdown, setSupplierSearch, showProductDropdown, showSupplierDropdown, supplierInputRef, supplierSearch, updateItemField }) {
  return (
    <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
      <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto" data-testid="purchase-dialog">
        <DialogHeader>
          <DialogTitle>{dialogTitle}</DialogTitle>
          <DialogDescription>{dialogDesc}</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="space-y-5 py-4">

            {/* 1. Supplier */}
            <div className="p-4 border rounded-lg space-y-2" ref={supplierInputRef}>
              <Label className="flex items-center gap-2 font-semibold">
                <Truck className="h-4 w-4" />
                1. Proveedor
              </Label>
              {selectedSupplier ? (
                <div className="flex items-center justify-between p-3 bg-accent/30 rounded-md">
                  <div>
                    <p className="font-medium">{selectedSupplier.name}</p>
                    <p className="text-xs text-muted-foreground">{selectedSupplier.contact_name || ''}</p>
                  </div>
                  {!isReadonly && (
                    <Button type="button" variant="outline" size="sm" onClick={() => { setSelectedSupplier(null); setSupplierSearch(''); }}>
                      Cambiar
                    </Button>
                  )}
                </div>
              ) : (
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Buscar proveedor... (mínimo 2 caracteres)"
                    value={supplierSearch}
                    onChange={(e) => { setSupplierSearch(e.target.value); setShowSupplierDropdown(true); }}
                    onFocus={() => setShowSupplierDropdown(true)}
                    className="pl-10"
                    disabled={isReadonly}
                    data-testid="supplier-search-input"
                  />
                  {showSupplierDropdown && supplierSearch.length >= 2 && (
                    <div className="absolute z-50 w-full mt-1 bg-popover border border-border rounded-md shadow-lg max-h-48 overflow-y-auto">
                      {filteredSuppliers.length > 0 ? filteredSuppliers.map((supplier) => (
                        <div
                          key={supplier.name}
                          className="px-4 py-2 cursor-pointer hover:bg-accent transition-colors"
                          onClick={() => handleSelectSupplier(supplier)}
                        >
                          <div className="font-medium">{supplier.name}</div>
                          {supplier.contact_name && <div className="text-xs text-muted-foreground">{supplier.contact_name}</div>}
                        </div>
                      )) : (
                        <div className="p-3 text-center text-muted-foreground text-sm">No se encontraron proveedores</div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* 2. Product Search */}
            {!isReadonly && (
              <div className="p-4 border rounded-lg space-y-2" ref={productInputRef}>
                <Label className="flex items-center gap-2 font-semibold">
                  <Package className="h-4 w-4" />
                  2. Agregar Productos
                </Label>
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Buscar producto por nombre o código..."
                    value={productSearch}
                    onChange={(e) => { setProductSearch(e.target.value); setShowProductDropdown(true); }}
                    onFocus={() => { if (productSearch.length >= 2) setShowProductDropdown(true); }}
                    className="pl-10"
                    data-testid="product-search-input"
                  />
                  {showProductDropdown && productSearch.length >= 2 && (
                    <div className="absolute z-50 w-full mt-1 bg-popover border border-border rounded-md shadow-lg max-h-48 overflow-y-auto">
                      {filteredProducts.length > 0 ? filteredProducts.map((product) => {
                        const inItems = items.find(i => i.barcode === product.barcode);
                        return (
                          <div
                            key={product.barcode}
                            className="px-4 py-2 cursor-pointer hover:bg-accent transition-colors flex justify-between items-center"
                            onClick={() => addProductToItems(product)}
                          >
                            <div>
                              <div className="font-medium">{product.name}</div>
                              <div className="text-xs text-muted-foreground font-mono">{product.barcode}</div>
                            </div>
                            <div className="text-right flex items-center gap-3">
                              <div>
                                <div className="text-sm font-mono">${product.purchase_price?.toLocaleString()}</div>
                                <div className="text-xs text-muted-foreground">Stock: {product.stock}</div>
                              </div>
                              {inItems && <span className="text-xs bg-primary/20 text-primary px-2 py-0.5 rounded">x{inItems.quantity}</span>}
                              <Button type="button" variant="outline" size="sm" className="h-7 text-xs" onClick={(e) => { e.stopPropagation(); addProductToItems(product); }}>
                                <Plus className="h-3 w-3 mr-1" />Agregar
                              </Button>
                            </div>
                          </div>
                        );
                      }) : (
                        <div className="p-3 text-center text-muted-foreground text-sm">No se encontraron productos</div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* 3. Items Table */}
            <div className="p-4 border rounded-lg space-y-3">
              <Label className="flex items-center gap-2 font-semibold">
                <ShoppingBag className="h-4 w-4" />
                {isReadonly ? '2' : '3'}. Detalle de Compra
                {items.length > 0 && <span className="text-xs bg-primary/20 text-primary px-2 py-0.5 rounded-full">{items.length} items</span>}
              </Label>

              {items.length === 0 ? (
                <div className="text-center py-6 text-muted-foreground">
                  <Package className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">Busca y agrega productos para comenzar</p>
                </div>
              ) : (
                <>
                  <div className="border rounded-md overflow-hidden">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Producto</TableHead>
                          <TableHead className="w-28 text-center">Cantidad</TableHead>
                          <TableHead className="w-36 text-center">Costo Unit.</TableHead>
                          <TableHead className="w-32 text-right">Total</TableHead>
                          {!isReadonly && <TableHead className="w-12"></TableHead>}
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {items.map((item) => (
                          <TableRow key={item.barcode}>
                            <TableCell>
                              <div className="font-medium">{item.product_name}</div>
                              <div className="text-xs text-muted-foreground font-mono">{item.barcode}</div>
                            </TableCell>
                            <TableCell>
                              {isReadonly ? (
                                <div className="text-center font-mono font-bold">{item.quantity}</div>
                              ) : (
                                <input
                                  type="number"
                                  min="1"
                                  className="w-20 text-center font-mono font-bold bg-transparent border rounded-md h-8 mx-auto block [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                                  value={item.quantity}
                                  onFocus={(e) => e.target.select()}
                                  onChange={(e) => {
                                    const val = e.target.value;
                                    if (val === '') {
                                      setItems(items.map(i => i.barcode === item.barcode ? { ...i, quantity: '' } : i));
                                    } else {
                                      setItemQuantity(item.barcode, val);
                                    }
                                  }}
                                  onBlur={(e) => {
                                    if (!e.target.value || parseInt(e.target.value) <= 0) setItemQuantity(item.barcode, 1);
                                  }}
                                  data-testid={`item-quantity-${item.barcode}`}
                                />
                              )}
                            </TableCell>
                            <TableCell>
                              {isReadonly ? (
                                <div className="text-center font-mono">${parseFloat(item.unit_cost).toLocaleString()}</div>
                              ) : (
                                <div className="flex items-center justify-center gap-1">
                                  <span className="text-muted-foreground">$</span>
                                  <input
                                    type="number"
                                    step="0.01"
                                    min="0"
                                    className="w-28 text-center font-mono bg-transparent border rounded-md h-8 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                                    value={item.unit_cost}
                                    onFocus={(e) => e.target.select()}
                                    onChange={(e) => updateItemField(item.barcode, 'unit_cost', e.target.value)}
                                    onBlur={(e) => { if (!e.target.value) updateItemField(item.barcode, 'unit_cost', 0); }}
                                    data-testid={`item-cost-${item.barcode}`}
                                  />
                                </div>
                              )}
                            </TableCell>
                            <TableCell className="text-right font-mono font-bold">
                              ${(parseFloat(item.total) || 0).toLocaleString()}
                            </TableCell>
                            {!isReadonly && (
                              <TableCell>
                                <Button type="button" variant="ghost" size="icon" className="h-8 w-8 text-destructive hover:text-destructive" onClick={() => removeItem(item.barcode)}>
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </TableCell>
                            )}
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                  <div className="flex justify-end pt-2 border-t">
                    <div className="text-right">
                      <span className="text-muted-foreground mr-3">Total Compra:</span>
                      <span className="text-2xl font-bold font-mono" data-testid="purchase-total">
                        ${calculateTotal().toLocaleString()}
                      </span>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={handleCloseDialog}>
              {isReadonly ? 'Cerrar' : 'Cancelar'}
            </Button>
            {!isReadonly && (
              <Button type="submit" disabled={isSubmitting || !selectedSupplier || items.length === 0} data-testid="save-purchase-button">
                {isSubmitting ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Guardando...
                  </>
                ) : (
                  dialogMode === 'edit' ? 'Actualizar Compra' : 'Guardar Borrador'
                )}
              </Button>
            )}
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
