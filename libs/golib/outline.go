// Copyright 2013 Chris McGee <sirnewton_01@yahoo.ca>. All rights reserved.
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.

// Modified by Todd Whiteman <toddw@activestate.com> for Komodo purposes.

package main

import (
	"encoding/xml"
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"path/filepath"
	"reflect"
	"time"
)

type Node interface {
}

type Import struct {
	XMLName xml.Name `xml:"import"`
	Module  string   `xml:"module,attr"`
	Name    string   `xml:"name,attr,omitempty"`
	Line    int      `xml:"line,attr,omitempty"`
	LineEnd int      `xml:"lineend,attr,omitempty"`
}

type Variable struct {
	XMLName xml.Name `xml:"variable"`
	Name    string   `xml:"name,attr"`
	Citdl   string   `xml:"citdl,attr"`
	Line    int      `xml:"line,attr,omitempty"`
	LineEnd int      `xml:"lineend,attr,omitempty"`
}

type Scope struct {
	XMLName   xml.Name `xml:"scope"`
	Classrefs string   `xml:"classrefs,attr,omitempty"`
	Ilk       string   `xml:"ilk,attr"`
	Name      string   `xml:"name,attr"`
	Lang      string   `xml:"lang,attr,omitempty"`
	Signature string   `xml:"signature,attr,omitempty"`
	Line      int      `xml:"line,attr,omitempty"`
	LineEnd   int      `xml:"lineend,attr,omitempty"`
	Nodes     []Node
}

type File struct {
	XMLName      xml.Name `xml:"file"`
	Lang         string   `xml:"lang,attr"`
	Path         string   `xml:"path,attr"`
	Mtime        int64    `xml:"mtime,attr"`
	FileScope    *Scope
	currentClass *Scope
}

func outlineHandler(path string) File {
	now := time.Now()
	outline := File{Lang: "Go", Path: path, Mtime: now.Unix()}
	filescope := Scope{Lang: "Go", Name: filepath.Base(path), Ilk: "blob"}
	outline.FileScope = &filescope
	fileset := token.NewFileSet()
	file, err := parser.ParseFile(fileset, path, nil, 0)

	if err != nil {
		fmt.Println("Error parsing go source:", err)
		return outline
	}

	ast.Inspect(file, func(n ast.Node) bool {
		switch x := n.(type) {
		case *ast.FuncDecl:
			if x.Pos().IsValid() {
				line := fileset.Position(x.Pos()).Line
				lineend := fileset.Position(x.End()).Line
				name := x.Name.Name
				if name != "" {
					signature := name
					if x.Recv.NumFields() > 0 {
						signature = signature + "(" + fileListStr(x.Recv) + ") "
					}

					signature = signature + name + "("
					if x.Type.Params.NumFields() > 0 {
						signature = signature + fileListStr(x.Type.Params)
					}
					signature = signature + ")"

					if x.Type.Results.NumFields() > 0 {
						if x.Type.Results.NumFields() == 1 {
							signature = signature + " " + fileListStr(x.Type.Results)
						} else {
							signature = signature + " (" + fileListStr(x.Type.Results) + ")"
						}
					}

					filescope.Nodes = append(filescope.Nodes, Scope{Ilk: "function", Name: name, Line: line, LineEnd: lineend, Signature: signature})
				}
			}
		case *ast.StructType:
			scope := outline.currentClass
			for _, field := range x.Fields.List {
				if field.Names != nil {
					line := fileset.Position(field.Pos()).Line
					name := string(field.Names[0].Name)
					citdl := typeStr(field.Type)
					scope.Nodes = append(scope.Nodes, Variable{Name: name, Citdl: citdl, Line: line})
				}
			}
		case *ast.GenDecl:
			if x.Tok == token.TYPE {
				for _, spec := range x.Specs {
					if spec.Pos().IsValid() {
						typeSpec, ok := spec.(*ast.TypeSpec)
						if ok {
							line := fileset.Position(spec.Pos()).Line
							lineend := fileset.Position(spec.End()).Line
							name := typeSpec.Name.Name
							outline.currentClass = &(Scope{Ilk: "class", Line: line, LineEnd: lineend, Name: name})
							filescope.Nodes = append(filescope.Nodes, outline.currentClass)
						}
					}
				}
			} else if x.Tok == token.IMPORT {
				for _, spec := range x.Specs {
					if spec.Pos().IsValid() {
						importSpec, ok := spec.(*ast.ImportSpec)
						if ok {
							line := fileset.Position(spec.Pos()).Line
							name := ""
							if importSpec.Name != nil {
								name = importSpec.Name.Name
							}
							path := importSpec.Path.Value[1 : len(importSpec.Path.Value)-1]
							filescope.Nodes = append(filescope.Nodes, Import{Line: line, Name: name, Module: path})
						}
					}
				}
			}
			//} else if x.Tok == token.CONST {
			//	line := strconv.FormatInt(int64(fileset.Position(x.Pos()).Line), 10)
			//	label := "CONST"
			//	filescope.Nodes = append(filescope.Nodes, Variable{Line: line, Citdl: citdl})
			//	filescope.Nodes = append(filescope.Nodes, Entry{Line: line, Label: label})
		}
		return true
	})

	return outline
}

func fileListStr(t *ast.FieldList) string {
	label := ""

	for argIdx, arg := range t.List {
		for nameIdx, name := range arg.Names {
			label = label + name.Name

			if nameIdx != len(arg.Names)-1 {
				label = label + ","
			}
		}

		if len(arg.Names) != 0 {
			label = label + " "
		}

		label = label + typeStr(arg.Type)

		if argIdx != len(t.List)-1 {
			label = label + ", "
		}
	}

	return label
}

func typeStr(t ast.Expr) string {
	switch e := t.(type) {
	case *ast.StarExpr:
		return "*" + typeStr(e.X)
	case *ast.Ident:
		return e.Name
	case *ast.SelectorExpr:
		return typeStr(e.X) + "." + e.Sel.Name
	case *ast.ArrayType:
		return "[]" + typeStr(e.Elt)
	default:
		return "<" + reflect.TypeOf(t).String() + ">"
	}
}

func main() {
	outline := outlineHandler(os.Args[1])
	output, err := xml.MarshalIndent(outline, "  ", "    ")
	if err != nil {
		fmt.Printf("error: %v\n", err)
	}
	fmt.Println(string(output))
}
